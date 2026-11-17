package com.retailops.api;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Service;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientResponseException;
import tools.jackson.databind.json.JsonMapper;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.*;
import java.util.*;
import static com.retailops.api.AppDtos.*;

@Service @Profile("integrated")
class ExternalServices {
    private final RestClient ml,airflow,tracking,minio;
    private final Path reader;
    private String accessToken;
    private Instant expires=Instant.EPOCH;
    ExternalServices(@Value("${retailops.app.ml-url}")String ml,@Value("${retailops.app.airflow-url}")String airflow,
                     @Value("${retailops.app.mlflow-url}")String tracking,@Value("${retailops.app.minio-url}")String minio,
                     @Value("${retailops.app.secrets-dir}")String secrets) {
        this.ml=client(ml).mutate().requestInterceptor((request, body, execution) -> {
            String identity=org.slf4j.MDC.get("request_id");
            if(identity!=null)request.getHeaders().set("X-Request-ID",identity);
            return execution.execute(request,body);
        }).build();this.airflow=client(airflow);this.tracking=client(tracking);this.minio=client(minio);
        this.reader=Path.of(secrets,"airflow_reader.json");
    }
    private static RestClient client(String base) {
        var uri=java.net.URI.create(base);
        if(!List.of("http","https").contains(uri.getScheme())||uri.getUserInfo()!=null||uri.getHost()==null)throw new IllegalArgumentException("URL de servicio inválida");
        var factory=new SimpleClientHttpRequestFactory();factory.setConnectTimeout(Duration.ofSeconds(2));factory.setReadTimeout(Duration.ofSeconds(15));
        return RestClient.builder().baseUrl(base).requestFactory(factory).build();
    }
    private static String health(RestClient client,String path) {
        try {client.get().uri(path).retrieve().toBodilessEntity();return "UP";} catch(Exception e){return "UNAVAILABLE";}
    }
    List<ServiceState> health() {
        return List.of(new ServiceState("fastapi",health(ml,"/health")),new ServiceState("mlflow",health(tracking,"/health")),
                       new ServiceState("minio",health(minio,"/minio/health/ready")),new ServiceState("airflow",health(airflow,"/api/v2/monitor/health")));
    }
    ModelRemote model() {
        try {
            var m=ml.get().uri("/model").retrieve().body(ModelRemote.class);
            if(m==null||!"1".equals(m.version())||!"retailops-sales-global".equals(m.name())||m.approved())
                throw new AppFailure(503,"MODEL_POLICY_MISMATCH","El modelo configurado no coincide con el candidato permitido");
            return m;
        } catch(AppFailure e){throw e;} catch(Exception e){throw new AppFailure(503,"ML_UNAVAILABLE","Servicio de inferencia no disponible");}
    }
    RemoteForecast predict(PredictionRequest request) {
        try {return ml.post().uri("/predict").body(Map.of("issue_date",request.issueDate().toString(),"store_nbr",request.storeNbr(),"family",request.family()))
                      .retrieve().body(RemoteForecast.class);
        } catch(RestClientResponseException e) {
            if(e.getStatusCode().value()==404)throw new AppFailure(404,"FEATURES_NOT_FOUND","Sin features para la selección solicitada");
            if(e.getStatusCode().value()==422)throw new AppFailure(400,"ML_INPUT_REJECTED","La selección no cumple el contrato temporal de inferencia");
            throw new AppFailure(503,"ML_UNAVAILABLE","Servicio de inferencia no disponible");
        } catch(Exception e){throw new AppFailure(503,"ML_UNAVAILABLE","Servicio de inferencia no disponible");}
    }
    @SuppressWarnings("unchecked")
    private synchronized String token(boolean refresh) throws Exception {
        if(!refresh&&accessToken!=null&&Instant.now().isBefore(expires))return accessToken;
        var credentials=JsonMapper.builder().build().readValue(Files.readString(reader),Map.class);
        var response=airflow.post().uri("/auth/token").body(Map.of("username",credentials.get("username"),"password",credentials.get("password")))
                            .retrieve().body(Map.class);
        accessToken=(String)response.get("access_token");expires=Instant.now().plusSeconds(240);
        if(accessToken==null)throw new IllegalStateException("Token ausente");
        return accessToken;
    }
    @SuppressWarnings("unchecked")
    private Map<String,Object> get(String path) throws Exception {
        try {return airflow.get().uri(path).header("Authorization","Bearer "+token(false)).retrieve().body(Map.class);}
        catch(RestClientResponseException e){
            if(e.getStatusCode().value()!=401)throw e;
            return airflow.get().uri(path).header("Authorization","Bearer "+token(true)).retrieve().body(Map.class);
        }
    }
    private static String safeString(Object value){return value==null?null:value.toString();}
    @SuppressWarnings("unchecked")
    Pipelines pipelines() {
        try {
            var list=new ArrayList<Pipeline>();var response=get("/api/v2/dags?limit=100");
            for(var dag:(List<Map<String,Object>>)response.get("dags")) {
                String id=(String)dag.get("dag_id");if(!Set.of("retailops_monthly_release","retailops_train_candidate","retailops_full_pipeline","retailops_validate_existing").contains(id))continue;
                var recent=new ArrayList<PipelineRun>();
                var runs=get("/api/v2/dags/"+id+"/dagRuns?limit=3&order_by=-run_after");
                for(var run:(List<Map<String,Object>>)runs.get("dag_runs"))recent.add(new PipelineRun((String)run.get("dag_run_id"),(String)run.get("state"),safeString(run.get("start_date")),safeString(run.get("end_date"))));
                list.add(new Pipeline(id,Boolean.TRUE.equals(dag.get("is_paused")),recent));
            }
            return new Pipelines("AVAILABLE",list);
        } catch(Exception e){throw new AppFailure(503,"AIRFLOW_UNAVAILABLE","No se pudo consultar el resumen de Airflow");}
    }
}
