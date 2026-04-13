FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

ARG UID=1000
ARG GID=1000
RUN groupadd -g $GID prometheus && \
    useradd -m -s /bin/bash -u $UID -g $GID prometheus

WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/
COPY agent_lib/ ./agent_lib/

RUN pip install --no-cache-dir -e .

RUN mkdir -p /app/runs && chown prometheus:prometheus /app/runs

USER prometheus

ENTRYPOINT ["pyre"]
