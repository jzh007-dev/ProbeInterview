"""Celery worker process entrypoint."""

from celery import Celery

from probeinterview.platform.foundation.infrastructure.logging import configure_logging
from probeinterview.platform.foundation.infrastructure.settings import Settings


def create_celery_app(settings: Settings | None = None) -> Celery:
    """Create the worker process after validating runtime configuration."""

    resolved_settings = settings or Settings()
    return Celery("probeinterview", broker=resolved_settings.celery_broker_url)


def main() -> None:
    """Run a Celery worker using the validated local configuration."""

    configure_logging()
    create_celery_app().worker_main(["worker", "--loglevel=INFO"])


if __name__ == "__main__":
    main()
