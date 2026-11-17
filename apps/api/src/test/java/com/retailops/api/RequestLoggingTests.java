package com.retailops.api;

import org.junit.jupiter.api.Test;
import org.slf4j.MDC;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import static org.junit.jupiter.api.Assertions.*;

class RequestLoggingTests {
    @Test void correlationIsBoundedAndCleaned() throws Exception {
        var filter = new RequestLoggingFilter();
        for (String supplied : new String[]{"a".repeat(32), "password=secret", "a".repeat(33)}) {
            var request = new MockHttpServletRequest();
            var response = new MockHttpServletResponse();
            request.addHeader("X-Request-ID", supplied);
            filter.doFilter(request, response, (req, res) -> {
                assertTrue(MDC.get("request_id").matches("[a-f0-9]{32}"));
                assertEquals(MDC.get("request_id"), response.getHeader("X-Request-ID"));
            });
            assertNull(MDC.get("request_id"));
            if (supplied.length() == 32) assertEquals(supplied, response.getHeader("X-Request-ID"));
        }
    }
}
