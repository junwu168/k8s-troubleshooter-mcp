import pytest
import requests


def test_health_endpoint_returns_200():
    """Health endpoint should return HTTP 200 when the server is up."""
    try:
        resp = requests.get("http://localhost:8000/health")
        assert resp.status_code == 200
    except requests.exceptions.RequestException as e:
        pytest.fail(f"Health endpoint not reachable: {e}")


def test_ready_endpoint_checks_k8s_connectivity():
    """Readiness endpoint should verify connectivity to Kubernetes cluster."""
    try:
        resp = requests.get("http://localhost:8000/ready")
        assert resp.status_code == 200
    except requests.exceptions.RequestException as e:
        pytest.fail(f"Ready endpoint not reachable: {e}")
