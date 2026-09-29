"""Celery worker process entrypoint."""

from celery import Celery

from probeinterview.platform.foundation.infrastructure.logging import configure_logging
from probeinterview.platform.foundation.infrastructure.settings import Settings
from probeinterview.platform.foundation.infrastructure.telemetry import (
    WORKER_SERVICE_NAME,
    initialize_telemetry,
)


def create_celery_app(settings: Settings | None = None) -> Celery:
    """Create the worker process after validating runtime configuration."""

    resolved_settings = settings or Settings()
    telemetry = initialize_telemetry(
        resolved_settings,
        service_name=WORKER_SERVICE_NAME,
    )
    configure_logging(service_resource=telemetry.resource)
    app = Celery("probeinterview", broker=resolved_settings.celery_broker_url)
    app.probeinterview_telemetry = telemetry
    return app


def main() -> None:
    """Run a Celery worker using the validated local configuration."""

    create_celery_app().worker_main(["worker", "--loglevel=INFO"])


if __name__ == "__main__":
    main()
