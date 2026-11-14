package com.retailops.api;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Service;
import java.util.*;
import static com.retailops.api.AppDtos.*;

@Service @Profile("integrated")
class PlatformService {
    private final HistoryService history;
    private final ExternalServices remote;
    private final boolean demo;
    PlatformService(HistoryService history,ExternalServices remote,@Value("${retailops.app.candidate-demo}") boolean demo){this.history=history;this.remote=remote;this.demo=demo;}
    Platform platform(){var state=history.state();var services=new ArrayList<ServiceState>();services.add(new ServiceState("postgresql","UP"));services.addAll(remote.health());return new Platform(state,services,"LOCAL_READ_ONLY");}
    ActiveModel model(){return new ActiveModel("NO_APPROVED_MODEL",demo,remote.model());}
    Forecast forecast(PredictionRequest r){
        if(!demo||!Boolean.TRUE.equals(r.candidateDemo()))throw new AppFailure(409,"NO_APPROVED_MODEL","No hay un modelo aprobado; activa explícitamente la demostración del candidato v1");
        var candidate=remote.model();var cutoff=history.state().cutoff();
        if(r.issueDate().isAfter(cutoff)||r.issueDate().isBefore(candidate.fitDate()))throw new AppFailure(400,"INVALID_ISSUE_DATE","Emisión anterior al ajuste o posterior al corte autorizado");
        var f=remote.predict(r);
        if(f==null||!"1".equals(f.modelVersion())||f.storeNbr()!=r.storeNbr()||!f.family().equals(r.family())||!f.issueDate().equals(r.issueDate())||f.predictions()==null||f.predictions().size()!=7)
            throw new AppFailure(502,"INVALID_FORECAST","Respuesta de inferencia incompatible");
        var points=new ArrayList<ForecastPoint>();
        for(int i=0;i<7;i++){
            var p=f.predictions().get(i);
            if(p.horizon()!=i+1||!r.issueDate().plusDays(i+1).equals(p.targetDate())||!Double.isFinite(p.prediction())||p.prediction()<0)
                throw new AppFailure(502,"INVALID_FORECAST","Respuesta de inferencia incompatible");
            points.add(new ForecastPoint(p.targetDate(),p.horizon(),p.prediction()));
        }
        return new Forecast(r.storeNbr(),r.family(),r.issueDate(),f.modelName(),f.modelVersion(),false,"CANDIDATE_DEMO",points);
    }
}
