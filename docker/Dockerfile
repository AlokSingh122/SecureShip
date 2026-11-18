# syntax=docker/dockerfile:1
# Build from the repository root:  docker build -f docker/Dockerfile -t secureship:local .

# ---- Stage 1: build dependencies in an isolated virtualenv ----
FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY app/requirements.txt .
RUN pip install -r requirements.txt

# ---- Stage 2: minimal runtime image ----
FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df AS runtime
ARG GIT_SHA=unknown
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    GIT_SHA=${GIT_SHA}

# Apply available OS security fixes, then drop package lists (smaller image, fewer CVEs).
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Dedicated unprivileged user with a numeric UID (required for non-root checks by some platforms).
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv
WORKDIR /srv
COPY app/ /srv/app/

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]

CMD ["uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "8000"]
