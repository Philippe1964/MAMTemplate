"""FastAPI application factory with Cloud-Native lifespan, correlation ID, and CORS."""

from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from mamtemplate.infrastructure.config.settings import get_settings
from mamtemplate.infrastructure.observability.correlation import (
    configure_structured_logging,
    set_request_id,
)
from mamtemplate.infrastructure.persistence.session import dispose_default_engine
from mamtemplate.presentation.health.health_router import router as health_router


@asynccontextmanager
async def app_lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Manage startup initialization and graceful shutdown of shared resources.

    Args:
        _app: The FastAPI application instance.

    Yields:
        Control back to FastAPI during application runtime.
    """
    configure_structured_logging()
    yield
    await dispose_default_engine()


def create_app() -> FastAPI:
    """Create and configure the Cloud-Native FastAPI application instance.

    Returns:
        The configured FastAPI application.
    """
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=app_lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def correlation_id_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Bind and echo X-Request-ID header for end-to-end Cloud-Native correlation."""
        incoming_id = request.headers.get("x-request-id")
        correlation_id = set_request_id(incoming_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = correlation_id
        return response

    app.include_router(health_router)
    return app


app = create_app()
