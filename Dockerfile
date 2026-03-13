FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./pyproject.toml

RUN pip install --upgrade pip setuptools wheel \
    && python -c "import subprocess, tomllib; from pathlib import Path; deps = tomllib.load(Path('pyproject.toml').open('rb'))['project']['dependencies']; subprocess.run(['pip', 'install', '--target=/install', *deps], check=True)"


FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app \
    HOME=/tmp \
    XDG_CACHE_HOME=/tmp/.cache

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --home-dir /home/appuser --uid 1000 --shell /usr/sbin/nologin appuser \
    && mkdir -p /tmp /app \
    && chown -R 1000:1000 /app /tmp /home/appuser

COPY --from=builder /install /usr/local/lib/python3.11/site-packages
COPY src ./src
COPY pyproject.toml ./pyproject.toml
COPY README.md ./README.md

USER 1000

VOLUME ["/tmp"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD ["curl", "--fail", "--silent", "http://127.0.0.1:8000/health"]

CMD ["python", "-m", "src.server"]
