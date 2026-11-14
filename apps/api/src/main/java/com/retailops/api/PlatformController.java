package com.retailops.api;

import org.springframework.context.annotation.Profile;
import org.springframework.web.bind.annotation.*;
import jakarta.validation.Valid;
import java.time.LocalDate;
import java.util.List;
import static com.retailops.api.AppDtos.*;

@RestController @Profile("integrated") @RequestMapping("/v1")
class PlatformController {
    private final HistoryService history;private final PlatformService platform;private final ExternalServices remote;
    PlatformController(HistoryService history,PlatformService platform,ExternalServices remote){this.history=history;this.platform=platform;this.remote=remote;}
    @GetMapping("/platform") Platform platform(){return platform.platform();}
    @GetMapping("/history/state") HistoricalState state(){return history.state();}
    @GetMapping("/history/batches") List<Batch> batches(){return history.batches();}
    @GetMapping("/catalog/stores") List<Integer> stores(){return history.stores();}
    @GetMapping("/catalog/families") List<String> families(){return history.families();}
    @GetMapping("/sales") SalesPage sales(@RequestParam int storeNbr,@RequestParam String family,@RequestParam LocalDate from,@RequestParam LocalDate to,@RequestParam(defaultValue="0")int page,@RequestParam(defaultValue="100")int size){return history.sales(storeNbr,family,from,to,page,size);}
    @GetMapping("/models/active") ActiveModel model(){return platform.model();}
    @GetMapping("/pipelines") Pipelines pipelines(){return remote.pipelines();}
    @PostMapping("/predictions") Forecast forecast(@Valid @RequestBody PredictionRequest request){return platform.forecast(request);}
}
