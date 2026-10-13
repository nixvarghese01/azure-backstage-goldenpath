package com.sportify.starter;

import static org.junit.jupiter.api.Assertions.assertEquals;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class StarterTest {
    @LocalServerPort int port;

    @Test void endpointsRespond() throws Exception {
        try (var client = HttpClient.newHttpClient()) {
            for (var path : new String[]{"/health/live", "/health/ready", "/v1/orders", "/docs"}) {
                var request = HttpRequest.newBuilder(URI.create("http://localhost:" + port + path)).GET().build();
                assertEquals(200, client.send(request, HttpResponse.BodyHandlers.ofString()).statusCode());
            }
        }
    }
}
