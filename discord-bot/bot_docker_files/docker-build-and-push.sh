#!/bin/bash

# === Load configuration from file ===
CONFIG_FILE="./docker-config.env"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Config file not found: $CONFIG_FILE"
    exit 1
fi

# Load variables
set -a
source "$CONFIG_FILE"
set +a

# === Derived Values ===
FULL_IMAGE_NAME="${REGISTRY}/${IMAGE_NAME}:${TAG}"

# === Build the image ===
echo "🚧 Building image: ${FULL_IMAGE_NAME}"
docker build -f "$DOCKERFILE" -t "$FULL_IMAGE_NAME" "$CONTEXT_DIR"

if [ $? -ne 0 ]; then
    echo "❌ Build failed."
    exit 1
fi

# === Push the image ===
echo "📤 Pushing image to registry: ${FULL_IMAGE_NAME}"
docker push "$FULL_IMAGE_NAME"

if [ $? -ne 0 ]; then
    echo "❌ Push failed. Make sure registry is reachable and insecure registry is configured (if HTTP)."
    exit 1
fi

echo "✅ Done: ${FULL_IMAGE_NAME} has been built and pushed."
