import logging
from collections.abc import Awaitable, Callable
from typing import cast
from uuid import uuid4

import uvicorn
from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from typing_extensions import override

from src.config import Settings, get_settings
from src.errors import ConfigError, K8sClientError
from src.lifecycle import AppContext, check_k8s_connectivity, create_lifespan
from src.logging_config import configure_logging, reset_correlation_id, set_correlation_id


def load_settings() -> Settings:
    try:
        return get_settings()
    except ValidationError as exc:
        raise ConfigError(
            "Invalid application configuration",
            details={"errors": [error["msg"] for error in exc.errors()]},
        ) from exc


settings = load_settings()
configure_logging(settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

mcp = FastMCP(
    name="k8s-troubleshooter-mcp",
    json_response=True,
    streamable_http_path="/",
)
mcp_http_app = mcp.streamable_http_app()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    @override
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        correlation_id = request.headers.get("x-correlation-id", str(uuid4()))
        token = set_correlation_id(correlation_id)
        request.state.correlation_id = correlation_id

        try:
            response = await call_next(request)
        finally:
            reset_correlation_id(token)

        response.headers["x-correlation-id"] = correlation_id
        return response


async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


async def ready(request: Request) -> JSONResponse:
    context = cast(AppContext, request.app.state.context)

    try:
        await check_k8s_connectivity(context, settings.NAMESPACE)
    except K8sClientError as exc:
        logger.warning("Kubernetes readiness check failed", extra={"error": str(exc)})
        return JSONResponse(exc.to_response().model_dump(), status_code=503)

    return JSONResponse({"status": "ready", "namespace": settings.NAMESPACE})


app = Starlette(
    routes=[
        Route("/health", health, methods=["GET"]),
        Route("/ready", ready, methods=["GET"]),
        Mount("/mcp", app=mcp_http_app),
    ],
    middleware=[Middleware(CorrelationIdMiddleware)],
    lifespan=create_lifespan(mcp, settings),
)


def main() -> None:
    logger.info(
        "Starting FastMCP server",
        extra={"host": settings.HOST, "port": settings.PORT},
    )
    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
        log_config=None,
    )


if __name__ == "__main__":
    main()
