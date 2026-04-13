FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*
RUN mkdir -p /workspace
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e .
ENTRYPOINT ["python", "-m", "agent"]
