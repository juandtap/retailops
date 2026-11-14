package com.retailops.api;

import org.flywaydb.core.Flyway;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.DependsOn;
import org.springframework.context.annotation.Profile;

/** Runner único de migraciones con propietarios e historiales separados. */
@Configuration(proxyBeanMethods = false)
@Profile("storage")
class StorageMigrationConfiguration {
    @Bean(initMethod = "migrate")
    Flyway controlFlyway(@Value("${retailops.storage.jdbc-url}") String url,
                         @Value("${pg_control_password}") String password) {
        return Flyway.configure().dataSource(url, "retailops_control_migrator", password)
                .defaultSchema("control").schemas("control").createSchemas(false)
                .locations("classpath:db/control").cleanDisabled(true).validateOnMigrate(true).load();
    }

    @Bean(initMethod = "migrate")
    @DependsOn("controlFlyway")
    Flyway dataFlyway(@Value("${retailops.storage.jdbc-url}") String url,
                      @Value("${pg_data_password}") String password) {
        return Flyway.configure().dataSource(url, "retailops_data_migrator", password)
                .defaultSchema("data_meta").schemas("data_meta", "silver", "gold", "training")
                .createSchemas(false).locations("classpath:db/data")
                .cleanDisabled(true).validateOnMigrate(true).load();
    }
}
