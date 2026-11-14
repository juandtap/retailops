package com.retailops.api;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import java.time.LocalDate;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import static com.retailops.api.AppDtos.*;
class PlatformApiTests {
 @Test void temporalBounds(){var cut=LocalDate.of(2014,12,31);assertThrows(AppFailure.class,()->HistoryService.validateWindow(1,"X",cut,cut.plusDays(1),0,100,cut));assertThrows(AppFailure.class,()->HistoryService.validateWindow(1,"X",LocalDate.of(2013,1,1),cut,0,100,cut));assertThrows(AppFailure.class,()->HistoryService.validateWindow(1,"X",cut,cut,0,10000,cut));}
 @Test void explicitCandidateConsent() throws Exception {
  var h=mock(HistoryService.class);var r=mock(ExternalServices.class);
  var mvc=MockMvcBuilders.standaloneSetup(new PlatformController(h,new PlatformService(h,r,true),r)).setControllerAdvice(new PlatformErrors()).build();
  mvc.perform(post("/v1/predictions").contentType("application/json").content("{\"issueDate\":\"2014-12-31\",\"storeNbr\":1,\"family\":\"GROCERY I\"}")).andExpect(status().isConflict()).andExpect(jsonPath("$.code").value("NO_APPROVED_MODEL"));verifyNoInteractions(r);
 }
 @Test void predictionAndUnavailableService() throws Exception {
  var h=mock(HistoryService.class);var r=mock(ExternalServices.class);var issue=LocalDate.of(2014,12,31);
  when(h.state()).thenReturn(new HistoricalState(issue,"bootstrap-2013-2014","RELEASED","COMPLETE"));
  when(r.model()).thenReturn(new ModelRemote("retailops-sales-global","1","test-run","sales-pit-v1",issue,LocalDate.of(2014,10,31),"candidate_local_preview",false,Map.of()));
  var points=new ArrayList<RemotePoint>();for(int i=1;i<=7;i++)points.add(new RemotePoint(issue.plusDays(i),i,1.25));
  when(r.predict(any())).thenReturn(new RemoteForecast(1,"GROCERY I",issue,"retailops-sales-global","1","sales-pit-v1",issue,points));
  var mvc=MockMvcBuilders.standaloneSetup(new PlatformController(h,new PlatformService(h,r,true),r)).setControllerAdvice(new PlatformErrors()).build();
  var body="{\"issueDate\":\"2014-12-31\",\"storeNbr\":1,\"family\":\"GROCERY I\",\"candidateDemo\":true}";
  mvc.perform(post("/v1/predictions").contentType("application/json").content(body)).andExpect(status().isOk()).andExpect(jsonPath("$.predictions.length()").value(7)).andExpect(jsonPath("$.productionApproved").value(false)).andExpect(jsonPath("$.predictions[6].targetDate").value("2015-01-07"));
  when(r.model()).thenThrow(new AppFailure(503,"ML_UNAVAILABLE","Servicio de inferencia no disponible"));
  mvc.perform(post("/v1/predictions").contentType("application/json").content(body)).andExpect(status().isServiceUnavailable()).andExpect(jsonPath("$.code").value("ML_UNAVAILABLE"));
 }
 @Test void invalidDate() throws Exception {
  var h=mock(HistoryService.class);var r=mock(ExternalServices.class);var mvc=MockMvcBuilders.standaloneSetup(new PlatformController(h,new PlatformService(h,r,false),r)).setControllerAdvice(new PlatformErrors()).build();
  mvc.perform(get("/v1/sales?storeNbr=1&family=X&from=invalid&to=2014-12-31")).andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value("INVALID_REQUEST"));verifyNoInteractions(h);
 }
}
