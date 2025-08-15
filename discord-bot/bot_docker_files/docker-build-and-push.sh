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

# === Tag and push 'latest' pointing to the same image ===
LATEST_IMAGE_NAME="${REGISTRY}/${IMAGE_NAME}:latest"
echo "🔄 Tagging ${FULL_IMAGE_NAME} as ${LATEST_IMAGE_NAME}"
docker tag "$FULL_IMAGE_NAME" "$LATEST_IMAGE_NAME"

echo "📤 Pushing image to registry: ${LATEST_IMAGE_NAME}"
docker push "$LATEST_IMAGE_NAME"

if [ $? -ne 0 ]; then
    echo "❌ Push of latest failed."
    exit 1
fi

echo "✅ Done: ${FULL_IMAGE_NAME} and ${LATEST_IMAGE_NAME} have been built and pushed."
