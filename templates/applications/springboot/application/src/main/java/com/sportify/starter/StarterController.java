package com.sportify.starter;

import java.util.List;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class StarterController {
    @GetMapping({"/health/live", "/health/ready"})
    public Map<String, String> health() {
        return Map.of("status", "ok", "backend", "demo");
    }

    @GetMapping("/v1/orders")
    public List<Map<String, Object>> orders() {
        return List.of(Map.of("id", "demo-001", "customerId", "cust-001", "currency", "GBP", "total", 5));
    }

    @GetMapping("/docs")
    public Map<String, Object> docs() {
        return Map.of("description", "Read-only Spring Boot starter",
            "endpoints", List.of("/health/live", "/health/ready", "/v1/orders"));
    }
}
