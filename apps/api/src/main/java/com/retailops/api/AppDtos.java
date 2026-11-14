package com.retailops.api;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.*;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;

public final class AppDtos {
    private AppDtos() {}
    public record HistoricalState(LocalDate cutoff, String lastBatch, String batchState, String publicationState) {}
    public record Batch(String id, String kind, LocalDate from, LocalDate to, long rows, String state, String publication) {}
    public record ServiceState(String name, String status) {}
    public record Platform(HistoricalState history, List<ServiceState> services, String accessMode) {}
    public record Sale(LocalDate date, BigDecimal sales) {}
    public record SalesPage(int storeNbr, String family, LocalDate from, LocalDate to, LocalDate cutoff,
                            int page, int size, long total, List<Sale> items) {}
    public record PredictionRequest(@NotNull LocalDate issueDate, @Min(1) @Max(32767) int storeNbr,
                                    @NotBlank @Size(max=120) String family, Boolean candidateDemo) {}
    public record ModelRemote(String name, String version, @JsonProperty("run_id") String runId,
                              @JsonProperty("feature_version") String featureVersion,
                              @JsonProperty("historical_cutoff") LocalDate cutoff,
                              @JsonProperty("fit_date") LocalDate fitDate,
                              String purpose, @JsonProperty("production_approved") boolean approved,
                              Map<String, Double> metrics) {}
    public record ActiveModel(String status, boolean demoEnabled, ModelRemote candidate) {}
    public record RemotePoint(@JsonProperty("target_date") LocalDate targetDate, int horizon, double prediction) {}
    public record RemoteForecast(@JsonProperty("store_nbr") int storeNbr, String family,
                                 @JsonProperty("issue_date") LocalDate issueDate,
                                 @JsonProperty("model_name") String modelName, @JsonProperty("model_version") String modelVersion,
                                 @JsonProperty("feature_version") String featureVersion,
                                 @JsonProperty("historical_cutoff") LocalDate cutoff, List<RemotePoint> predictions) {}
    public record ForecastPoint(LocalDate targetDate, int horizon, double prediction) {}
    public record Forecast(int storeNbr,String family,LocalDate issueDate,String modelName,String modelVersion,
                           boolean productionApproved,String mode,List<ForecastPoint> predictions) {}
    public record PipelineRun(String id,String state,String startedAt,String finishedAt) {}
    public record Pipeline(String id,boolean paused,List<PipelineRun> recentRuns) {}
    public record Pipelines(String status,List<Pipeline> dags) {}
    public record ApiError(String code,String message) {}
}
