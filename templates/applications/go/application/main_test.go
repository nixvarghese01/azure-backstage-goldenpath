package main

import (
    "encoding/json"
    "net/http/httptest"
    "testing"
)

func TestStarterContract(t *testing.T) {
    for _, path := range []string{"/health/live", "/health/ready", "/v1/orders", "/docs"} {
        response := httptest.NewRecorder()
        handler().ServeHTTP(response, httptest.NewRequest("GET", path, nil))
        if response.Code != 200 || !json.Valid(response.Body.Bytes()) {
            t.Fatalf("%s: %d %s", path, response.Code, response.Body.String())
        }
    }
    response := httptest.NewRecorder()
    handler().ServeHTTP(response, httptest.NewRequest("POST", "/v1/orders", nil))
    if response.Code != 405 {
        t.Fatalf("read-only endpoint accepted POST: %d", response.Code)
    }
}
