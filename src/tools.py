# pyright: basic, reportUnusedFunction=false

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable

from mcp.server.fastmcp import Context, FastMCP


logger = logging.getLogger(__name__)


def _serialize(value: Any) -> str:
    if isinstance(value, list):
        payload = [_to_jsonable(item) for item in value]
    else:
        payload = _to_jsonable(value)
    return json.dumps(payload, default=str)


def _to_jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    return value


def _get_k8s_client(ctx: Context | None) -> Any:
    if ctx is None or getattr(ctx, "request_context", None) is None:
        raise RuntimeError("MCP request context is unavailable.")

    app_context = getattr(ctx.request_context, "lifespan_context", None)
    if app_context is None:
        raise RuntimeError("MCP lifespan context is unavailable.")

    k8s_client = getattr(app_context, "k8s_client", None)
    if k8s_client is not None:
        return k8s_client

    startup_error = getattr(app_context, "startup_error", None)
    if startup_error:
        raise RuntimeError(startup_error)

    raise RuntimeError("Kubernetes client is unavailable in lifespan context.")


async def _run_tool(action: str, operation: Callable[[], Any]) -> str:
    try:
        return _serialize(await asyncio.to_thread(operation))
    except Exception as exc:
        logger.exception("Failed to %s", action)
        raise RuntimeError(f"Failed to {action}: {exc}") from exc


def register_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    async def list_pods(
        namespace: str,
        label_selector: str | None = None,
        ctx: Context | None = None,
    ) -> str:
        """List pods in a namespace with optional label selector."""

        k8s = _get_k8s_client(ctx)
        return await _run_tool(
            f"list pods in namespace '{namespace}'",
            lambda: k8s.list_pods(namespace, label_selector),
        )

    @mcp.tool()
    async def list_deployments(namespace: str, ctx: Context | None = None) -> str:
        """List deployments in a namespace."""

        k8s = _get_k8s_client(ctx)
        return await _run_tool(
            f"list deployments in namespace '{namespace}'",
            lambda: k8s.list_deployments(namespace),
        )

    @mcp.tool()
    async def list_services(namespace: str, ctx: Context | None = None) -> str:
        """List services in a namespace."""

        k8s = _get_k8s_client(ctx)
        return await _run_tool(
            f"list services in namespace '{namespace}'",
            lambda: k8s.list_services(namespace),
        )

    @mcp.tool()
    async def list_nodes(ctx: Context | None = None) -> str:
        """List cluster nodes."""

        k8s = _get_k8s_client(ctx)
        return await _run_tool("list cluster nodes", k8s.list_nodes)

    @mcp.tool()
    async def list_events(namespace: str, ctx: Context | None = None) -> str:
        """List events in a namespace."""

        k8s = _get_k8s_client(ctx)
        return await _run_tool(
            f"list events in namespace '{namespace}'",
            lambda: k8s.list_events(namespace),
        )

    @mcp.tool()
    async def get_pod_logs(
        pod_name: str,
        namespace: str,
        container: str | None = None,
        tail_lines: int = 100,
        ctx: Context | None = None,
    ) -> str:
        """Get pod logs with optional container selection."""

        k8s = _get_k8s_client(ctx)
        return await _run_tool(
            f"get pod logs for '{pod_name}' in namespace '{namespace}'",
            lambda: k8s.get_pod_logs(pod_name, namespace, container, tail_lines),
        )

    @mcp.tool()
    async def get_resource_yaml(
        kind: str,
        name: str,
        namespace: str,
        ctx: Context | None = None,
    ) -> str:
        """Get resource YAML for a Kubernetes object."""

        k8s = _get_k8s_client(ctx)
        return await _run_tool(
            f"get resource YAML for {kind} '{name}'",
            lambda: k8s.get_resource_yaml(kind, name, namespace),
        )

    @mcp.tool()
    async def describe_pod(
        pod_name: str,
        namespace: str,
        ctx: Context | None = None,
    ) -> str:
        """Describe a pod and include related events."""

        k8s = _get_k8s_client(ctx)
        return await _run_tool(
            f"describe pod '{pod_name}' in namespace '{namespace}'",
            lambda: k8s.describe_pod(pod_name, namespace),
        )

    @mcp.tool()
    async def describe_deployment(
        name: str,
        namespace: str,
        ctx: Context | None = None,
    ) -> str:
        """Describe a deployment and include related events."""

        k8s = _get_k8s_client(ctx)
        return await _run_tool(
            f"describe deployment '{name}' in namespace '{namespace}'",
            lambda: k8s.describe_deployment(name, namespace),
        )

    @mcp.tool()
    async def describe_service(
        name: str,
        namespace: str,
        ctx: Context | None = None,
    ) -> str:
        """Describe a service and include related events."""

        k8s = _get_k8s_client(ctx)
        return await _run_tool(
            f"describe service '{name}' in namespace '{namespace}'",
            lambda: k8s.describe_service(name, namespace),
        )


__all__ = ["register_tools"]
