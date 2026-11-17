package com.retailops.api;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.UUID;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/** Correlación acotada; no registra URL, cuerpo, credenciales ni mensaje de excepción. */
@Component
public class RequestLoggingFilter extends OncePerRequestFilter {
    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String supplied = request.getHeader("X-Request-ID");
        String identity = supplied != null && supplied.matches("[a-f0-9]{32}")
                ? supplied : UUID.randomUUID().toString().replace("-", "");
        var logger = LoggerFactory.getLogger(RequestLoggingFilter.class);
        try (var ignored = MDC.putCloseable("request_id", identity)) {
            response.setHeader("X-Request-ID", identity);
            try {
                chain.doFilter(request, response);
                (response.getStatus() >= 500 ? logger.atError() : logger.atInfo())
                    .addKeyValue("timestamp", java.time.Instant.now().toString())
                    .addKeyValue("status", response.getStatus()).log("Solicitud HTTP completada");
            } catch (IOException | ServletException | RuntimeException error) {
                logger.atError().addKeyValue("timestamp", java.time.Instant.now().toString()).addKeyValue("status", 500)
                      .addKeyValue("exception_type", error.getClass().getSimpleName()).log("Solicitud HTTP fallida");
                throw error;
            }
        }
    }
}
