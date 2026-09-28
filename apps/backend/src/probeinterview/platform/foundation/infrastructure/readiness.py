"""Runtime dependency checks used by the readiness endpoint."""

from collections.abc import Callable

from celery import Celery
from sqlalchemy import create_engine, text

from probeinterview.platform.foundation.infrastructure.settings import Settings

ReadinessCheck = Callable[[], None]


def build_readiness_checks(settings: Settings) -> dict[str, ReadinessCheck]:
    """Build connection-only checks that do not depend on application schemas."""

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    celery_app = Celery("probeinterview-readiness", broker=settings.celery_broker_url)

    def check_database() -> None:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def check_task_queue() -> None:
        with celery_app.connection_for_write() as connection:
            connection.ensure_connection(max_retries=0)

    return {
        "database": check_database,
        "task_queue": check_task_queue,
    }
