from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PodInfo(BaseModel):
    name: str
    namespace: str
    phase: str
    node_name: str | None = None
    pod_ip: str | None = None
    host_ip: str | None = None
    start_time: datetime | None = None
    labels: dict[str, str] = Field(default_factory=dict)
    containers: list[str] = Field(default_factory=list)
    ready_containers: int = 0
    total_containers: int = 0
    restart_count: int = 0


class DeploymentInfo(BaseModel):
    name: str
    namespace: str
    replicas: int = 0
    ready_replicas: int = 0
    available_replicas: int = 0
    updated_replicas: int = 0
    labels: dict[str, str] = Field(default_factory=dict)
    selector: dict[str, str] = Field(default_factory=dict)
    creation_timestamp: datetime | None = None


class ServiceInfo(BaseModel):
    name: str
    namespace: str
    service_type: str
    cluster_ip: str | None = None
    external_ips: list[str] = Field(default_factory=list)
    ports: list[str] = Field(default_factory=list)
    selector: dict[str, str] = Field(default_factory=dict)
    creation_timestamp: datetime | None = None


class NodeInfo(BaseModel):
    name: str
    status: str
    roles: list[str] = Field(default_factory=list)
    labels: dict[str, str] = Field(default_factory=dict)
    kubelet_version: str | None = None
    os_image: str | None = None
    kernel_version: str | None = None
    container_runtime_version: str | None = None
    creation_timestamp: datetime | None = None


class EventInfo(BaseModel):
    name: str
    namespace: str | None = None
    type: str | None = None
    reason: str | None = None
    message: str
    involved_object_kind: str | None = None
    involved_object_name: str | None = None
    count: int = 0
    first_timestamp: datetime | None = None
    last_timestamp: datetime | None = None
    event_time: datetime | None = None


class LogResponse(BaseModel):
    pod_name: str
    namespace: str
    container: str | None = None
    tail_lines: int = 100
    logs: str = ""
    error: str | None = None


class ResourceYAMLResponse(BaseModel):
    kind: str
    name: str
    namespace: str | None = None
    yaml_content: str | None = None
    error: str | None = None


class DescribeResponse(BaseModel):
    kind: str
    name: str
    namespace: str | None = None
    yaml_content: str | None = None
    events: list[EventInfo] = Field(default_factory=list)
    error: str | None = None
