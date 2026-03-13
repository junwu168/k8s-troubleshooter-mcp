import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import cast

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette

from src.config import Settings
from src.errors import K8sClientError
from src.k8s_client import K8sClient


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AppContext:
    k8s_client: K8sClient | None = None
    startup_error: str | None = None


async def initialize_k8s_client(settings: Settings) -> AppContext:
    def _initialize() -> AppContext:
        k8s_client = K8sClient(kubeconfig_path=settings.KUBECONFIG_PATH)
        if k8s_client.auth_error is not None:
            raise K8sClientError(k8s_client.auth_error)

        return AppContext(k8s_client=k8s_client)

    try:
        return await asyncio.to_thread(_initialize)
    except K8sClientError:
        raise
    except Exception as exc:
        raise K8sClientError("Unable to initialize Kubernetes client") from exc


async def close_app_context(context: AppContext | None) -> None:
    if context is None or context.k8s_client is None:
        return

    await asyncio.to_thread(context.k8s_client.close)


async def check_k8s_connectivity(context: AppContext, namespace: str) -> None:
    if context.k8s_client is None:
        raise K8sClientError(context.startup_error or "Kubernetes client is not initialized")
    if context.k8s_client.core_v1 is None:
        raise K8sClientError("Kubernetes core API client is not initialized")

    try:
        list_namespaced_pod = cast(
            Callable[..., object],
            context.k8s_client.core_v1.list_namespaced_pod,
        )
        _ = await asyncio.to_thread(
            list_namespaced_pod,
            namespace=namespace,
            limit=1,
            _request_timeout=5,
        )
    except Exception as exc:
        raise K8sClientError(
            f"Kubernetes readiness check failed for namespace '{namespace}'"
        ) from exc


def create_mcp_lifespan(
    settings: Settings,
) -> Callable[[FastMCP], AbstractAsyncContextManager[AppContext]]:
    @asynccontextmanager
    async def lifespan(_server: FastMCP) -> AsyncIterator[AppContext]:
        try:
            context = await initialize_k8s_client(settings)
            logger.info("MCP lifespan initialized", extra={"namespace": settings.NAMESPACE})
        except K8sClientError as exc:
            context = AppContext(startup_error=str(exc))
            logger.warning(
                "MCP lifespan started without Kubernetes connectivity",
                extra={"error": str(exc), "namespace": settings.NAMESPACE},
            )

        try:
            yield context
        finally:
            await close_app_context(context)
            logger.info("MCP lifespan shutdown completed")

    return lifespan


def create_lifespan(
    mcp: FastMCP,
    settings: Settings,
) -> Callable[[Starlette], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(mcp.session_manager.run())

            try:
                app.state.context = await initialize_k8s_client(settings)
                logger.info(
                    "Application startup completed",
                    extra={"namespace": settings.NAMESPACE},
                )
            except K8sClientError as exc:
                app.state.context = AppContext(startup_error=str(exc))
                logger.warning(
                    "Application startup completed with degraded Kubernetes connectivity",
                    extra={"error": str(exc), "namespace": settings.NAMESPACE},
                )

            try:
                yield
            finally:
                await close_app_context(app.state.context)
                logger.info("Application shutdown completed")

    return lifespan
