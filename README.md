# k8s-troubleshooter-mcp

A Model Context Protocol (MCP) server for Kubernetes troubleshooting, built with Python 3.11.

## Description

This MCP server provides AI agents with read-only access to Kubernetes clusters via standardized MCP tools. It runs as a Kubernetes deployment with proper RBAC configuration, allowing safe troubleshooting operations.

## Features

- **Read-Only K8s Operations**: List pods, deployments, services, nodes, events
- **Pod Logs**: Retrieve container logs with tail line limits
- **Resource Inspection**: Get YAML output and describe resources with events
- **Health Endpoints**: `/health` and `/ready` for Kubernetes probes
- **Structured Logging**: JSON-formatted logs with correlation IDs
- **Security**: Runs as non-root user with minimal RBAC permissions

## MCP Tools

| Tool | Description |
|------|-------------|
| `list_pods` | List pods in a namespace with optional label selector |
| `list_deployments` | List deployments in a namespace |
| `list_services` | List services in a namespace |
| `list_nodes` | List all nodes in the cluster |
| `list_events` | List events in a namespace |
| `get_pod_logs` | Get logs from a pod (with container and tail_lines options) |
| `get_resource_yaml` | Get YAML representation of any resource |
| `describe_pod` | Get detailed pod info with events |
| `describe_deployment` | Get detailed deployment info with events |
| `describe_service` | Get detailed service info with events |

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Run the server
python -m src.server

# The server will be available at http://localhost:8000
# Health check: curl http://localhost:8000/health
# Ready check: curl http://localhost:8000/ready
# MCP endpoint: curl http://localhost:8000/mcp
```

### Docker Build

```bash
# Build the image
docker build -t k8s-troubleshooter-mcp:latest .

# Run locally (requires KUBECONFIG)
docker run -p 8000:8000 -v ~/.kube:/home/appuser/.kube:ro k8s-troubleshooter-mcp:latest
```

### Kubernetes Deployment

```bash
# Create namespace and deploy
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/serviceaccount.yaml
kubectl apply -f k8s/role.yaml
kubectl apply -f k8s/rolebinding.yaml
kubectl apply -f k8s/clusterrole.yaml
kubectl apply -f k8s/clusterrolebinding.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml

# Verify deployment
kubectl get pods -n k8s-troubleshooter
kubectl logs -n k8s-troubleshooter -l app=k8s-troubleshooter-mcp
```

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `PORT` | `8000` | Server port |
| `HOST` | `0.0.0.0` | Server host |
| `NAMESPACE` | `k8s-troubleshooter` | Default namespace for operations |
| `KUBECONFIG_PATH` | - | Path to kubeconfig (optional, uses in-cluster config if not set) |

## Architecture

```
┌─────────────────┐
│   MCP Client    │
│ (e.g., Claude)  │
└────────┬────────┘
         │ HTTP/SSE
         ▼
┌─────────────────┐
│  K8s Troubleshooter MCP  │
│  Server (Python/FastMCP) │
└────────┬────────┘
         │ Kubernetes API
         ▼
┌─────────────────┐
│   K8s Cluster   │
└─────────────────┘
```

## Security

- **Non-root container**: Runs as UID 1000
- **Read-only root filesystem**: Container runs with read-only root
- **RBAC**: Least-privilege Role with only read verbs (get, list, watch)
- **No secrets access**: ServiceAccount cannot read secrets
- **Namespace scoped**: Access limited to specific namespace

## Project Structure

```
.
├── src/
│   ├── __init__.py
│   ├── server.py           # FastMCP server and HTTP routes
│   ├── tools.py            # MCP tool implementations
│   ├── k8s_client.py       # Kubernetes client wrapper
│   ├── schemas.py          # Pydantic models
│   ├── config.py           # Configuration management
│   ├── lifecycle.py        # App lifespan management
│   ├── logging_config.py   # Structured logging setup
│   └── errors.py           # Custom exceptions
├── k8s/
│   ├── namespace.yaml      # k8s-troubleshooter namespace
│   ├── serviceaccount.yaml # Service account
│   ├── role.yaml           # RBAC Role (read-only)
│   ├── rolebinding.yaml    # Role binding
│   ├── deployment.yaml     # Deployment manifest
│   └── service.yaml        # Service manifest
├── tests/                  # Test suite
├── Dockerfile              # Multi-stage build
├── pyproject.toml          # Python dependencies
└── README.md               # This file
```

## Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing
```

## License

MIT
