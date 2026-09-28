"""FastAPI process entrypoint."""

from fastapi import FastAPI

from probeinterview.platform.foundation.infrastructure.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the API process after validating runtime configuration."""

    resolved_settings = settings or Settings()
    app = FastAPI(title="ProbeInterview API")
    app.state.settings = resolved_settings
    return app
