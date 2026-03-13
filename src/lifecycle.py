import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import cast

from kubernetes import client, config  # pyright: ignore[reportMissingTypeStubs]
from kubernetes.config.config_exception import (  # pyright: ignore[reportMissingTypeStubs]
    ConfigException,
)
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette

from src.config import Settings
from src.errors import K8sClientError


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AppContext:
    k8s_client: client.CoreV1Api | None = None
    api_client: client.ApiClient | None = None
    startup_error: str | None = None


async def initialize_k8s_client(settings: Settings) -> AppContext:
    def _initialize() -> AppContext:
        if settings.KUBECONFIG_PATH:
            load_kube_config = cast(Callable[..., None], config.load_kube_config)
            load_kube_config(config_file=settings.KUBECONFIG_PATH)
        else:
            try:
                load_incluster_config = cast(Callable[..., None], config.load_incluster_config)
                load_incluster_config()
            except ConfigException:
                load_kube_config = cast(Callable[..., None], config.load_kube_config)
                load_kube_config()

        api_client = client.ApiClient()
        return AppContext(
            k8s_client=client.CoreV1Api(api_client),
            api_client=api_client,
        )

    try:
        return await asyncio.to_thread(_initialize)
    except ConfigException as exc:
        raise K8sClientError("Unable to load Kubernetes configuration") from exc
    except Exception as exc:
        raise K8sClientError("Unable to initialize Kubernetes client") from exc


async def close_app_context(context: AppContext | None) -> None:
    if context is None or context.api_client is None:
        return

    await asyncio.to_thread(context.api_client.close)


async def check_k8s_connectivity(context: AppContext, namespace: str) -> None:
    if context.k8s_client is None:
        raise K8sClientError(context.startup_error or "Kubernetes client is not initialized")

    try:
        list_namespaced_pod = cast(Callable[..., object], context.k8s_client.list_namespaced_pod)
        await asyncio.to_thread(
            list_namespaced_pod,
            namespace=namespace,
            limit=1,
            _request_timeout=5,
        )
    except Exception as exc:
        raise K8sClientError(
            f"Kubernetes readiness check failed for namespace '{namespace}'"
        ) from exc


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
