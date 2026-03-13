"""MCP tools for Kubernetes troubleshooting."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from mcp.server.fastmcp import Context

if TYPE_CHECKING:
    from .k8s_client import K8sClient
    from .lifecycle import AppContext

logger = logging.getLogger(__name__)


def _get_k8s_client(ctx: Context) -> "K8sClient":
    """Extract K8s client from MCP context."""
    app_ctx: AppContext = ctx.request_context.lifespan_context
    return app_ctx.k8s_client


async def list_pods(
    namespace: str,
    label_selector: str | None = None,
    ctx: Context = None,
) -> str:
    """List pods in a namespace with optional label selector.

    Args:
        namespace: The Kubernetes namespace to list pods from
        label_selector: Optional label selector to filter pods (e.g., "app=nginx")
    """
    k8s = _get_k8s_client(ctx)
    pods = k8s.list_pods(namespace, label_selector)
    return json.dumps([pod.model_dump() for pod in pods], indent=2)


async def list_deployments(
    namespace: str,
    ctx: Context = None,
) -> str:
    """List deployments in a namespace.

    Args:
        namespace: The Kubernetes namespace to list deployments from
    """
    k8s = _get_k8s_client(ctx)
    deployments = k8s.list_deployments(namespace)
    return json.dumps([d.model_dump() for d in deployments], indent=2)


async def list_services(
    namespace: str,
    ctx: Context = None,
) -> str:
    """List services in a namespace.

    Args:
        namespace: The Kubernetes namespace to list services from
    """
    k8s = _get_k8s_client(ctx)
    services = k8s.list_services(namespace)
    return json.dumps([s.model_dump() for s in services], indent=2)


async def list_nodes(
    ctx: Context = None,
) -> str:
    """List all nodes in the cluster."""
    k8s = _get_k8s_client(ctx)
    nodes = k8s.list_nodes()
    return json.dumps([n.model_dump() for n in nodes], indent=2)


async def list_events(
    namespace: str,
    ctx: Context = None,
) -> str:
    """List events in a namespace.

    Args:
        namespace: The Kubernetes namespace to list events from
    """
    k8s = _get_k8s_client(ctx)
    events = k8s.list_events(namespace)
    return json.dumps([e.model_dump() for e in events], indent=2)


async def get_pod_logs(
    pod_name: str,
    namespace: str,
    container: str | None = None,
    tail_lines: int = 100,
    ctx: Context = None,
) -> str:
    """Get logs from a pod.

    Args:
        pod_name: Name of the pod to get logs from
        namespace: The Kubernetes namespace where the pod exists
        container: Optional container name (required if pod has multiple containers)
        tail_lines: Number of lines to retrieve from the end of the logs (default: 100)
    """
    k8s = _get_k8s_client(ctx)
    logs = k8s.get_pod_logs(pod_name, namespace, container, tail_lines)
    return json.dumps(logs.model_dump(), indent=2)


async def get_resource_yaml(
    kind: str,
    name: str,
    namespace: str,
    ctx: Context = None,
) -> str:
    """Get YAML representation of a Kubernetes resource.

    Args:
        kind: Resource kind (Pod, Deployment, Service, etc.)
        name: Name of the resource
        namespace: The Kubernetes namespace where the resource exists
    """
    k8s = _get_k8s_client(ctx)
    yaml_response = k8s.get_resource_yaml(kind, name, namespace)
    return json.dumps(yaml_response.model_dump(), indent=2)


async def describe_pod(
    pod_name: str,
    namespace: str,
    ctx: Context = None,
) -> str:
    """Describe a pod with details and recent events.

    Args:
        pod_name: Name of the pod to describe
        namespace: The Kubernetes namespace where the pod exists
    """
    k8s = _get_k8s_client(ctx)
    describe = k8s.describe_resource("Pod", pod_name, namespace)
    return json.dumps(describe.model_dump(), indent=2)


async def describe_deployment(
    name: str,
    namespace: str,
    ctx: Context = None,
) -> str:
    """Describe a deployment with details and recent events.

    Args:
        name: Name of the deployment to describe
        namespace: The Kubernetes namespace where the deployment exists
    """
    k8s = _get_k8s_client(ctx)
    describe = k8s.describe_resource("Deployment", name, namespace)
    return json.dumps(describe.model_dump(), indent=2)


async def describe_service(
    name: str,
    namespace: str,
    ctx: Context = None,
) -> str:
    """Describe a service with details and recent events.

    Args:
        name: Name of the service to describe
        namespace: The Kubernetes namespace where the service exists
    """
    k8s = _get_k8s_client(ctx)
    describe = k8s.describe_resource("Service", name, namespace)
    return json.dumps(describe.model_dump(), indent=2)
