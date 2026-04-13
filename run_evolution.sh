#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="prometheus-evolution"
RUNS_DIR="$(pwd)/runs"

MODEL="${MODEL:-gpt-4.1-mini}"
GENERATIONS="${GENERATIONS:-3}"
BEAM_SIZE="${BEAM_SIZE:-2}"
MUTATIONS="${MUTATIONS:-2}"

if [ -z "${LITELLM_API_KEY:-}" ]; then
    echo "Error: LITELLM_API_KEY is not set" >&2
    exit 1
fi
if [ -z "${LITELLM_BASE_URL:-}" ]; then
    echo "Error: LITELLM_BASE_URL is not set" >&2
    exit 1
fi

mkdir -p "$RUNS_DIR"
chmod 777 "$RUNS_DIR"

echo "=== Source code checksum (before) ==="
SRC_HASH_BEFORE=$(find src/ -type f -name '*.py' -exec sha256sum {} + | sort | sha256sum | cut -d' ' -f1)
echo "$SRC_HASH_BEFORE"

echo "=== Building Docker image ==="
docker build -t "$IMAGE_NAME" \
    --build-arg UID="$(id -u)" \
    --build-arg GID="$(id -g)" \
    .

echo "=== Running evolution ==="
echo "Model: $MODEL via LiteLLM ($LITELLM_BASE_URL)"
echo "Generations: $GENERATIONS, Beam: $BEAM_SIZE, Mutations: $MUTATIONS"
echo ""

docker run --rm \
    --read-only \
    --tmpfs /tmp:size=512m \
    --tmpfs /home/prometheus:size=64m \
    -v "$RUNS_DIR:/app/runs" \
    --cap-drop ALL \
    --security-opt no-new-privileges \
    --cpus 2 \
    --memory 2g \
    -e OPENAI_API_KEY="$LITELLM_API_KEY" \
    "$IMAGE_NAME" \
    run \
    --api-format openai \
    --base-url "$LITELLM_BASE_URL" \
    --model "$MODEL" \
    --generations "$GENERATIONS" \
    --beam-size "$BEAM_SIZE" \
    --mutations-per-parent "$MUTATIONS" \
    --output-dir /app/runs

echo ""
echo "=== Source code checksum (after) ==="
SRC_HASH_AFTER=$(find src/ -type f -name '*.py' -exec sha256sum {} + | sort | sha256sum | cut -d' ' -f1)
echo "$SRC_HASH_AFTER"

if [ "$SRC_HASH_BEFORE" = "$SRC_HASH_AFTER" ]; then
    echo "✓ Source code UNCHANGED"
else
    echo "✗ WARNING: Source code was modified!"
    exit 1
fi

echo ""
echo "=== Results ==="
ls -la "$RUNS_DIR"/
