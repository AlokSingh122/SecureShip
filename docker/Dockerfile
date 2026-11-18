# syntax=docker/dockerfile:1
# Build from the repository root:  docker build -f docker/Dockerfile -t secureship:local .

FROM alpine:3.24@sha256:f59abe656b692d901e184be3445e084786602108599d2a51d229c0f5a48c71bf
ARG GIT_SHA=unknown
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    GIT_SHA=${GIT_SHA}

RUN apk update \
    && apk upgrade --no-cache \
    && apk add --no-cache python3 py3-pip \
    && rm -rf /var/cache/apk/*

RUN python3 -m venv --without-pip /opt/venv \
    && python3 -m pip --python /opt/venv install --upgrade pip==26.3
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY app/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

RUN addgroup -S -g 10001 app \
    && adduser -S -u 10001 -G app -H -s /sbin/nologin app

WORKDIR /srv
COPY app/ /srv/app/

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]

CMD ["uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "8000"]
