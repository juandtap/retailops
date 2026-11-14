package com.retailops.api;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Service;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.*;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.*;
import static com.retailops.api.AppDtos.*;

@Service @Profile("integrated")
class HistoryService {
    private final String url;
    private final Path secret;
    HistoryService(@Value("${retailops.app.jdbc-url}") String url,@Value("${retailops.app.secrets-dir}") String secrets) {
        if(!url.startsWith("jdbc:postgresql://") || url.contains("password=")) throw new IllegalArgumentException("APP_DB_URL inválida");
        this.url=url;this.secret=Path.of(secrets,"pg_api_password");
    }
    interface Read<T> {T execute(Connection c) throws Exception;}
    private <T> T read(Read<T> operation) {
        try(Connection c=DriverManager.getConnection(url,"retailops_api",Files.readString(secret).strip())) {
            c.setReadOnly(true);c.setAutoCommit(false);
            try {return operation.execute(c);} finally {c.rollback();}
        } catch(AppFailure e){throw e;} catch(Exception e){throw new AppFailure(503,"HISTORY_UNAVAILABLE","No se pudo consultar el histórico autorizado");}
    }
    HistoricalState state() {
        return read(c->{try(var s=c.prepareStatement("SELECT h.released_through,h.last_batch_id,b.state,p.status FROM control.historical_state h JOIN control.batches b ON b.batch_id=h.last_batch_id JOIN control.publications p USING(batch_id)")) {
            s.setQueryTimeout(5);try(var r=s.executeQuery()) {
                if(!r.next())throw new AppFailure(503,"HISTORY_NOT_READY","No hay un histórico publicado");
                return new HistoricalState(r.getObject(1,LocalDate.class),r.getString(2),r.getString(3),r.getString(4));
            }} });
    }
    List<Batch> batches() {
        return read(c->{var list=new ArrayList<Batch>();try(var s=c.prepareStatement("SELECT b.batch_id,b.kind,b.period_start,b.period_end,b.row_count,b.state,p.status FROM control.batches b JOIN control.publications p USING(batch_id) CROSS JOIN control.historical_state h WHERE b.state='RELEASED' AND p.status='COMPLETE' AND b.period_end<=h.released_through ORDER BY b.period_start LIMIT 40")) {
            s.setQueryTimeout(5);try(var r=s.executeQuery()){while(r.next())list.add(new Batch(r.getString(1),r.getString(2),r.getObject(3,LocalDate.class),r.getObject(4,LocalDate.class),r.getLong(5),r.getString(6),r.getString(7)));}}
            return list;});
    }
    List<Integer> stores() {
        return read(c->{var list=new ArrayList<Integer>();try(var s=c.prepareStatement("SELECT DISTINCT store_nbr FROM training.sales ORDER BY store_nbr LIMIT 100")){s.setQueryTimeout(5);try(var r=s.executeQuery()){while(r.next())list.add(r.getInt(1));}}return list;});
    }
    List<String> families() {
        return read(c->{var list=new ArrayList<String>();try(var s=c.prepareStatement("SELECT DISTINCT family FROM training.sales ORDER BY family LIMIT 100")){s.setQueryTimeout(5);try(var r=s.executeQuery()){while(r.next())list.add(r.getString(1));}}return list;});
    }
    static void validateWindow(int store,String family,LocalDate from,LocalDate to,int page,int size,LocalDate cutoff) {
        if(store<1||store>32767||family==null||family.isBlank()||family.length()>120||from==null||to==null||
           from.isBefore(LocalDate.of(2013,1,1))||to.isAfter(cutoff)||from.isAfter(to)||ChronoUnit.DAYS.between(from,to)>365||page<0||page>1000||size<1||size>200)
            throw new AppFailure(400,"INVALID_HISTORY_WINDOW","Fechas o filtros inválidos: máximo 366 días y sin superar el corte autorizado");
    }
    SalesPage sales(int store,String family,LocalDate from,LocalDate to,int page,int size) {
        var cutoff=state().cutoff();validateWindow(store,family,from,to,page,size,cutoff);
        return read(c->{long total;var list=new ArrayList<Sale>();String where=" FROM training.sales WHERE store_nbr=? AND family=? AND date BETWEEN ? AND ?";
            try(var s=c.prepareStatement("SELECT count(*)"+where)){bind(s,store,family,from,to);try(var r=s.executeQuery()){r.next();total=r.getLong(1);}}
            try(var s=c.prepareStatement("SELECT date,sales"+where+" ORDER BY date LIMIT ? OFFSET ?")){bind(s,store,family,from,to);s.setInt(5,size);s.setInt(6,page*size);try(var r=s.executeQuery()){while(r.next())list.add(new Sale(r.getObject(1,LocalDate.class),r.getBigDecimal(2)));}}
            return new SalesPage(store,family,from,to,cutoff,page,size,total,list);
        });
    }
    private static void bind(PreparedStatement s,int store,String family,LocalDate from,LocalDate to)throws SQLException {
        s.setQueryTimeout(5);s.setInt(1,store);s.setString(2,family);s.setObject(3,from);s.setObject(4,to);
    }
}
