# pyright: basic, reportMissingTypeStubs=false

from __future__ import annotations

from typing import Any, TypeVar

import yaml
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from kubernetes.config.config_exception import ConfigException

from .schemas import (
    DeploymentInfo,
    DescribeResponse,
    EventInfo,
    LogResponse,
    NodeInfo,
    PodInfo,
    ResourceYAMLResponse,
    ServiceInfo,
)

T = TypeVar("T")


class K8sClient:
    def __init__(self, kubeconfig_path: str | None = None) -> None:
        self.api_client: client.ApiClient | None = None
        self.core_v1: client.CoreV1Api | None = None
        self.apps_v1: client.AppsV1Api | None = None
        self.auth_error: str | None = None
        self.config_source: str | None = None
        self.kubeconfig_path = kubeconfig_path

        self._load_config()

    def close(self) -> None:
        if self.api_client is not None:
            self.api_client.close()

    def is_ready(self) -> bool:
        if self.auth_error is not None:
            return False

        try:
            version_api = client.VersionApi(self._require(self.api_client))
            version_api.get_code()
        except ApiException:
            return False
        except Exception:
            return False

        return True

    def list_pods(
        self,
        namespace: str,
        label_selector: str | None = None,
    ) -> list[PodInfo]:
        try:
            pods = self._require(self.core_v1).list_namespaced_pod(
                namespace=namespace,
                label_selector=label_selector,
            )
        except ApiException as exc:
            raise RuntimeError(
                f"Failed to list pods in namespace '{namespace}': {exc.reason}"
            ) from exc

        items: list[PodInfo] = []
        for pod in pods.items:
            metadata = pod.metadata
            pod_status = pod.status
            pod_spec = pod.spec
            container_statuses = pod_status.container_statuses if pod_status else None
            containers = pod_spec.containers if pod_spec else []
            items.append(
                PodInfo(
                    name=metadata.name,
                    namespace=metadata.namespace,
                    phase=pod_status.phase if pod_status and pod_status.phase else "Unknown",
                    node_name=pod_spec.node_name if pod_spec else None,
                    pod_ip=pod_status.pod_ip if pod_status else None,
                    host_ip=pod_status.host_ip if pod_status else None,
                    start_time=pod_status.start_time if pod_status else None,
                    labels=metadata.labels or {},
                    containers=[container.name for container in containers or []],
                    ready_containers=sum(
                        1 for status in (container_statuses or []) if status.ready
                    ),
                    total_containers=len(containers or []),
                    restart_count=sum(
                        status.restart_count for status in (container_statuses or [])
                    ),
                )
            )

        return items

    def list_deployments(self, namespace: str) -> list[DeploymentInfo]:
        try:
            deployments = self._require(self.apps_v1).list_namespaced_deployment(
                namespace=namespace,
            )
        except ApiException as exc:
            raise RuntimeError(
                f"Failed to list deployments in namespace '{namespace}': {exc.reason}"
            ) from exc

        items: list[DeploymentInfo] = []
        for deployment in deployments.items:
            metadata = deployment.metadata
            status = deployment.status
            spec = deployment.spec
            selector = spec.selector.match_labels if spec and spec.selector else {}
            items.append(
                DeploymentInfo(
                    name=metadata.name,
                    namespace=metadata.namespace,
                    replicas=spec.replicas if spec and spec.replicas else 0,
                    ready_replicas=status.ready_replicas if status and status.ready_replicas else 0,
                    available_replicas=(
                        status.available_replicas
                        if status and status.available_replicas
                        else 0
                    ),
                    updated_replicas=(
                        status.updated_replicas if status and status.updated_replicas else 0
                    ),
                    labels=metadata.labels or {},
                    selector=selector,
                    creation_timestamp=metadata.creation_timestamp,
                )
            )

        return items

    def list_services(self, namespace: str) -> list[ServiceInfo]:
        try:
            services = self._require(self.core_v1).list_namespaced_service(
                namespace=namespace,
            )
        except ApiException as exc:
            raise RuntimeError(
                f"Failed to list services in namespace '{namespace}': {exc.reason}"
            ) from exc

        items: list[ServiceInfo] = []
        for service in services.items:
            metadata = service.metadata
            spec = service.spec
            ports = [self._format_service_port(port) for port in (spec.ports if spec else []) or []]
            items.append(
                ServiceInfo(
                    name=metadata.name,
                    namespace=metadata.namespace,
                    service_type=spec.type if spec and spec.type else "ClusterIP",
                    cluster_ip=spec.cluster_ip if spec else None,
                    external_ips=self._extract_service_external_ips(service),
                    ports=ports,
                    selector=spec.selector if spec and spec.selector else {},
                    creation_timestamp=metadata.creation_timestamp,
                )
            )

        return items

    def list_nodes(self) -> list[NodeInfo]:
        try:
            nodes = self._require(self.core_v1).list_node()
        except ApiException as exc:
            raise RuntimeError(f"Failed to list nodes: {exc.reason}") from exc

        items: list[NodeInfo] = []
        for node in nodes.items:
            metadata = node.metadata
            labels = metadata.labels or {}
            node_info = node.status.node_info if node.status else None
            items.append(
                NodeInfo(
                    name=metadata.name,
                    status=self._node_ready_status(node),
                    roles=self._extract_node_roles(labels),
                    labels=labels,
                    kubelet_version=node_info.kubelet_version if node_info else None,
                    os_image=node_info.os_image if node_info else None,
                    kernel_version=node_info.kernel_version if node_info else None,
                    container_runtime_version=(
                        node_info.container_runtime_version if node_info else None
                    ),
                    creation_timestamp=metadata.creation_timestamp,
                )
            )

        return items

    def list_events(self, namespace: str) -> list[EventInfo]:
        try:
            events = self._require(self.core_v1).list_namespaced_event(namespace=namespace)
        except ApiException as exc:
            raise RuntimeError(
                f"Failed to list events in namespace '{namespace}': {exc.reason}"
            ) from exc

        return [self._build_event_info(event) for event in events.items]

    def get_pod_logs(
        self,
        pod_name: str,
        namespace: str,
        container: str | None = None,
        tail_lines: int = 100,
    ) -> LogResponse:
        try:
            logs = self._require(self.core_v1).read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                container=container,
                tail_lines=tail_lines,
            )
        except RuntimeError as exc:
            return LogResponse(
                pod_name=pod_name,
                namespace=namespace,
                container=container,
                tail_lines=tail_lines,
                error=str(exc),
            )
        except ApiException as exc:
            return LogResponse(
                pod_name=pod_name,
                namespace=namespace,
                container=container,
                tail_lines=tail_lines,
                error=f"Failed to get logs for pod '{pod_name}': {exc.reason}",
            )

        return LogResponse(
            pod_name=pod_name,
            namespace=namespace,
            container=container,
            tail_lines=tail_lines,
            logs=logs,
        )

    def get_resource_yaml(
        self,
        kind: str,
        name: str,
        namespace: str,
    ) -> ResourceYAMLResponse:
        try:
            resource, kind_label = self._read_resource(
                kind=kind,
                name=name,
                namespace=namespace,
            )
            yaml_content = yaml.safe_dump(
                self._sanitize_resource(resource),
                sort_keys=False,
            )
        except RuntimeError as exc:
            return ResourceYAMLResponse(
                kind=kind,
                name=name,
                namespace=namespace,
                error=str(exc),
            )
        except ValueError as exc:
            return ResourceYAMLResponse(
                kind=kind,
                name=name,
                namespace=namespace,
                error=str(exc),
            )
        except ApiException as exc:
            return ResourceYAMLResponse(
                kind=kind,
                name=name,
                namespace=namespace,
                error=(
                    f"Failed to get {kind.lower()} '{name}' in namespace "
                    f"'{namespace}': {exc.reason}"
                ),
            )

        return ResourceYAMLResponse(
            kind=kind_label,
            name=name,
            namespace=namespace,
            yaml_content=yaml_content,
        )

    def describe_pod(self, pod_name: str, namespace: str) -> DescribeResponse:
        return self.describe_resource(kind="pod", name=pod_name, namespace=namespace)

    def describe_deployment(self, name: str, namespace: str) -> DescribeResponse:
        return self.describe_resource(kind="deployment", name=name, namespace=namespace)

    def describe_service(self, name: str, namespace: str) -> DescribeResponse:
        return self.describe_resource(kind="service", name=name, namespace=namespace)

    def describe_resource(
        self,
        kind: str,
        name: str,
        namespace: str,
    ) -> DescribeResponse:
        yaml_response = self.get_resource_yaml(kind=kind, name=name, namespace=namespace)
        if yaml_response.error is not None:
            return DescribeResponse(
                kind=kind,
                name=name,
                namespace=namespace,
                error=yaml_response.error,
            )

        try:
            events = self._list_related_events(kind=kind, name=name, namespace=namespace)
        except RuntimeError as exc:
            return DescribeResponse(
                kind=kind,
                name=name,
                namespace=namespace,
                yaml_content=yaml_response.yaml_content,
                error=str(exc),
            )
        except ValueError as exc:
            return DescribeResponse(
                kind=kind,
                name=name,
                namespace=namespace,
                yaml_content=yaml_response.yaml_content,
                error=str(exc),
            )
        except ApiException as exc:
            return DescribeResponse(
                kind=kind,
                name=name,
                namespace=namespace,
                yaml_content=yaml_response.yaml_content,
                error=f"Failed to list related events: {exc.reason}",
            )

        return DescribeResponse(
            kind=yaml_response.kind,
            name=name,
            namespace=namespace,
            yaml_content=yaml_response.yaml_content,
            events=events,
        )

    def _load_config(self) -> None:
        incluster_error: str | None = None
        kubeconfig_error: str | None = None

        try:
            if self.kubeconfig_path is not None:
                config.load_kube_config(config_file=self.kubeconfig_path)
                self.config_source = "kubeconfig"
            else:
                config.load_incluster_config()
                self.config_source = "in-cluster"
        except ConfigException as exc:
            if self.kubeconfig_path is not None:
                incluster_error = "not attempted"
                kubeconfig_error = str(exc)
            else:
                incluster_error = str(exc)
                try:
                    config.load_kube_config()
                    self.config_source = "kubeconfig"
                except ConfigException as kube_exc:
                    kubeconfig_error = str(kube_exc)

        if self.config_source is None:
            self.auth_error = (
                "Unable to load Kubernetes configuration. "
                f"In-cluster config failed: {incluster_error}. "
                f"Kubeconfig failed: {kubeconfig_error}."
            )
            return

        self.api_client = client.ApiClient()
        self.core_v1 = client.CoreV1Api(self.api_client)
        self.apps_v1 = client.AppsV1Api(self.api_client)

    def _require(self, value: T | None) -> T:
        if value is None:
            raise RuntimeError(self.auth_error or "Kubernetes client is not configured.")
        return value

    def _read_resource(
        self,
        kind: str,
        name: str,
        namespace: str,
    ) -> tuple[Any, str]:
        normalized_kind, kind_label = self._normalize_kind(kind)

        if normalized_kind == "pod":
            return (
                self._require(self.core_v1).read_namespaced_pod(
                    name=name,
                    namespace=namespace,
                ),
                kind_label,
            )
        if normalized_kind == "deployment":
            return (
                self._require(self.apps_v1).read_namespaced_deployment(
                    name=name,
                    namespace=namespace,
                ),
                kind_label,
            )
        if normalized_kind == "service":
            return (
                self._require(self.core_v1).read_namespaced_service(
                    name=name,
                    namespace=namespace,
                ),
                kind_label,
            )
        if normalized_kind == "node":
            return self._require(self.core_v1).read_node(name=name), kind_label

        raise ValueError(f"Unsupported resource kind: {kind}")

    def _normalize_kind(self, kind: str) -> tuple[str, str]:
        normalized = kind.strip().lower()
        mapping = {
            "pod": ("pod", "Pod"),
            "pods": ("pod", "Pod"),
            "deployment": ("deployment", "Deployment"),
            "deployments": ("deployment", "Deployment"),
            "service": ("service", "Service"),
            "services": ("service", "Service"),
            "node": ("node", "Node"),
            "nodes": ("node", "Node"),
        }

        if normalized not in mapping:
            raise ValueError(f"Unsupported resource kind: {kind}")

        return mapping[normalized]

    def _sanitize_resource(self, resource: Any) -> dict[str, Any]:
        sanitized = self._require(self.api_client).sanitize_for_serialization(resource)
        if not isinstance(sanitized, dict):
            raise ValueError("Unexpected Kubernetes resource payload")
        return sanitized

    def _list_related_events(
        self,
        kind: str,
        name: str,
        namespace: str,
    ) -> list[EventInfo]:
        normalized_kind, kind_label = self._normalize_kind(kind)
        field_selector = f"involvedObject.name={name},involvedObject.kind={kind_label}"

        if normalized_kind == "node":
            events = self._require(self.core_v1).list_event_for_all_namespaces(
                field_selector=field_selector,
            )
        else:
            events = self._require(self.core_v1).list_namespaced_event(
                namespace=namespace,
                field_selector=field_selector,
            )

        return [self._build_event_info(event) for event in events.items]

    def _build_event_info(self, event: Any) -> EventInfo:
        metadata = event.metadata
        involved_object = event.involved_object
        return EventInfo(
            name=metadata.name,
            namespace=metadata.namespace,
            type=event.type,
            reason=event.reason,
            message=event.message or "",
            involved_object_kind=involved_object.kind if involved_object else None,
            involved_object_name=involved_object.name if involved_object else None,
            count=event.count or 0,
            first_timestamp=event.first_timestamp,
            last_timestamp=event.last_timestamp,
            event_time=event.event_time,
        )

    def _node_ready_status(self, node: Any) -> str:
        conditions = node.status.conditions if node.status else None
        if not conditions:
            return "Unknown"

        for condition in conditions:
            if condition.type == "Ready":
                return "Ready" if condition.status == "True" else "NotReady"

        return "Unknown"

    def _extract_node_roles(self, labels: dict[str, str]) -> list[str]:
        roles = [
            key.removeprefix("node-role.kubernetes.io/")
            for key in labels
            if key.startswith("node-role.kubernetes.io/")
        ]
        legacy_role = labels.get("kubernetes.io/role")
        if legacy_role:
            roles.append(legacy_role)

        if not roles:
            return ["worker"]

        return sorted(set(role or "worker" for role in roles))

    def _extract_service_external_ips(
        self,
        service: Any,
    ) -> list[str]:
        spec = service.spec
        external_ips = list(getattr(spec, "external_i_ps", []) or [])
        ingress = (
            service.status.load_balancer.ingress
            if service.status and service.status.load_balancer
            else []
        )

        for item in ingress or []:
            if item.hostname:
                external_ips.append(item.hostname)
            elif item.ip:
                external_ips.append(item.ip)

        return sorted(set(external_ips))

    def _format_service_port(self, port: Any) -> str:
        target_port = port.target_port if port.target_port is not None else port.port
        name_prefix = f"{port.name}:" if port.name else ""
        protocol = port.protocol or "TCP"
        return f"{name_prefix}{port.port}/{protocol}->{target_port}"
