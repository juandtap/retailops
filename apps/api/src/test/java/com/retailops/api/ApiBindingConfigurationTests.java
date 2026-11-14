package com.retailops.api;

import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class ApiBindingConfigurationTests {
    @Test
    void rejectsEmptyHostAndInvalidPort() {
        assertThatThrownBy(() -> new ApiBindingConfiguration(" ", 8080))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("API_HOST");
        for (int port : new int[]{-1, 65536}) {
            assertThatThrownBy(() -> new ApiBindingConfiguration("127.0.0.1", port))
                    .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("API_PORT");
        }
    }

    @Test
    void acceptsLocalAndEphemeralPorts() {
        for (int port : new int[]{0, 8080}) {
            assertThatCode(() -> new ApiBindingConfiguration("127.0.0.1", port)).doesNotThrowAnyException();
        }
    }
}
