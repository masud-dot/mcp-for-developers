"""Tracing setup. The SDK emits spans; this exports them."""

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from mcpdev.config import settings


def configure_tracing(service: str) -> None:
    """Install an exporter. Until you do, spans are a no-op."""
    provider = TracerProvider(
        resource=Resource.create({
            "service.name": service,
            "service.version": "1.0.0",
            "deployment.environment": settings.environment,
        })
    )
    if settings.otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.http import (
            trace_exporter as otlp,
        )

        provider.add_span_processor(
            BatchSpanProcessor(
                otlp.OTLPSpanExporter(
                    endpoint=settings.otlp_endpoint
                )
            )
        )
    trace.set_tracer_provider(provider)
