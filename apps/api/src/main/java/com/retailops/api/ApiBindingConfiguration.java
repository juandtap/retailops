package com.retailops.api;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;

/** Valida el enlace HTTP antes de iniciar el servidor. El puerto cero permite pruebas aisladas. */
@Configuration(proxyBeanMethods = false)
class ApiBindingConfiguration {
    ApiBindingConfiguration(@Value("${server.address}") String host,
                            @Value("${server.port}") int port) {
        if (host == null || host.isBlank()) {
            throw new IllegalArgumentException("API_HOST no puede estar vacío");
        }
        if (port < 0 || port > 65535) {
            throw new IllegalArgumentException("API_PORT debe estar entre 0 y 65535");
        }
    }
}
