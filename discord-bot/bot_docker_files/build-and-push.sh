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

# === Load version from version.py ===
VERSION_FILE="../bot/version.py"
if [ ! -f "$VERSION_FILE" ]; then
    echo "❌ Version file not found: $VERSION_FILE"
    exit 1
fi

MESHBOT_VERSION=$(python -c "import sys; sys.path.insert(0, '../bot'); from version import __version__; print(__version__)" 2>/dev/null)
if [ -z "$MESHBOT_VERSION" ]; then
    echo "❌ Could not extract version from $VERSION_FILE"
    exit 1
fi

# === Use MESHBOT_VERSION for Docker tag ===
TAG="$MESHBOT_VERSION"
FULL_IMAGE_NAME="${REGISTRY}/${IMAGE_NAME}:${TAG}"
LATEST_IMAGE_NAME="${REGISTRY}/${IMAGE_NAME}:latest"

# === Setup buildx for multi-platform builds ===
BUILDER_NAME="multiarch-builder"
echo "🔧 Setting up buildx builder for multi-platform builds"

# Create builder if it doesn't exist
if ! docker buildx inspect "$BUILDER_NAME" >/dev/null 2>&1; then
    echo "📦 Creating new buildx builder: $BUILDER_NAME"
    docker buildx create --name "$BUILDER_NAME" --driver docker-container --bootstrap
fi

# Use the builder
docker buildx use "$BUILDER_NAME"

# === Build and push multi-platform images ===
echo "🚧 Building and pushing multi-platform image: ${FULL_IMAGE_NAME}"
echo "🎯 Target platforms: linux/amd64, linux/arm64/v8"

docker buildx build \
    --platform linux/amd64,linux/arm64/v8 \
    -f "$DOCKERFILE" \
    -t "$FULL_IMAGE_NAME" \
    -t "$LATEST_IMAGE_NAME" \
    --push \
    "$CONTEXT_DIR"

if [ $? -ne 0 ]; then
    echo "❌ Multi-platform build and push failed."
    exit 1
fi

echo "✅ Done: Multi-platform images ${FULL_IMAGE_NAME} and ${LATEST_IMAGE_NAME} have been built and pushed."
echo "📋 Supported platforms: linux/amd64, linux/arm64/v8"
