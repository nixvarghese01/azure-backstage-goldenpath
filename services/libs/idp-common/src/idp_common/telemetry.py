"""Explicit OpenTelemetry setup (FastAPI 0.143 no longer auto-configures exporters; see COMPATIBILITY.md)."""

from __future__ import annotations

import os


def configure_tracing(service_name: str) -> None:
    """Enable OTLP trace export when OTEL_EXPORTER_OTLP_ENDPOINT is set; otherwise do nothing."""
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return
    # Avoid loading the exporter and protobuf stack when tracing is not configured.
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
