package main

import (
    "context"
    "encoding/json"
    "log"
    "net/http"
    "os"
    "os/signal"
    "syscall"
    "time"
)

func handler() http.Handler {
    mux := http.NewServeMux()
    health := func(w http.ResponseWriter, r *http.Request) {
        w.Header().Set("Content-Type", "application/json")
        json.NewEncoder(w).Encode(map[string]string{"status": "ok", "backend": "demo"})
    }
    mux.HandleFunc("GET /health/live", health)
    mux.HandleFunc("GET /health/ready", health)
    mux.HandleFunc("GET /v1/orders", func(w http.ResponseWriter, r *http.Request) {
        w.Header().Set("Content-Type", "application/json")
        json.NewEncoder(w).Encode([]map[string]any{
            {"id": "demo-001", "customerId": "cust-001", "currency": "GBP", "total": 5},
        })
    })
    mux.HandleFunc("GET /docs", func(w http.ResponseWriter, r *http.Request) {
        w.Header().Set("Content-Type", "application/json")
        json.NewEncoder(w).Encode(map[string]any{
            "description": "Read-only Go starter API",
            "endpoints": []string{"/health/live", "/health/ready", "/v1/orders"},
        })
    })
    return mux
}

func main() {
    ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
    defer cancel()
    server := &http.Server{
        Addr: ":3000", Handler: handler(), ReadHeaderTimeout: 5 * time.Second,
        ReadTimeout: 15 * time.Second, WriteTimeout: 15 * time.Second, IdleTimeout: 60 * time.Second,
    }
    go func() {
        <-ctx.Done()
        shutdown, stop := context.WithTimeout(context.Background(), 10*time.Second)
        defer stop()
        if err := server.Shutdown(shutdown); err != nil {
            log.Printf("shutdown: %v", err)
        }
    }()
    if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
        log.Fatal(err)
    }
}
