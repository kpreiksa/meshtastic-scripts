#!/bin/bash

# Build and push script for docker_bot_updater

set -e  # Exit on any error

# === Configuration ===
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/docker-config.env"

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Configuration file not found: $CONFIG_FILE"
    echo "Please create the configuration file with required variables."
    exit 1
fi

# Load variables
set -a
source "$CONFIG_FILE"
set +a

# === Validate required variables ===
if [ -z "$REGISTRY" ] || [ -z "$IMAGE_NAME" ] || [ -z "$DOCKERFILE" ] || [ -z "$CONTEXT_DIR" ]; then
    echo "❌ Missing required variables in $CONFIG_FILE"
    echo "Required: REGISTRY, IMAGE_NAME, DOCKERFILE, CONTEXT_DIR"
    exit 1
fi

# === Generate version tag ===
# Use current timestamp as version for docker_bot_updater
VERSION=$(date +"%Y%m%d-%H%M%S")
TAG="$VERSION"
FULL_IMAGE_NAME="${REGISTRY}/${IMAGE_NAME}:${TAG}"
LATEST_IMAGE_NAME="${REGISTRY}/${IMAGE_NAME}:latest"

echo "📋 Build Configuration:"
echo "   Registry: $REGISTRY"
echo "   Image: $IMAGE_NAME"
echo "   Tag: $TAG"
echo "   Dockerfile: $DOCKERFILE"
echo "   Context: $CONTEXT_DIR"
echo ""

# === Test registry connectivity ===
echo "🔍 Testing registry connectivity..."
if curl -f -s "http://$REGISTRY/v2/" > /dev/null; then
    echo "✅ Registry is reachable"
else
    echo "⚠️  Registry connectivity test failed, but continuing..."
    echo "   This might be normal if the registry requires authentication"
fi
echo ""

# === Build the image ===
echo "🚧 Building image: ${FULL_IMAGE_NAME}"
docker build -f "$DOCKERFILE" -t "$FULL_IMAGE_NAME" "$CONTEXT_DIR"

if [ $? -ne 0 ]; then
    echo "❌ Build failed."
    exit 1
fi

# === Tag as latest ===
echo "🏷️  Tagging as latest: ${LATEST_IMAGE_NAME}"
docker tag "$FULL_IMAGE_NAME" "$LATEST_IMAGE_NAME"

# === Push the versioned image ===
echo "📤 Pushing versioned image to registry: ${FULL_IMAGE_NAME}"
docker push "$FULL_IMAGE_NAME"

if [ $? -ne 0 ]; then
    echo "❌ Push failed for versioned image."
    exit 1
fi

# === Push the latest image ===
echo "📤 Pushing latest image to registry: ${LATEST_IMAGE_NAME}"

# Add retry logic for the latest push (sometimes fails on network issues)
RETRY_COUNT=3
for i in $(seq 1 $RETRY_COUNT); do
    echo "🔄 Push attempt $i of $RETRY_COUNT for latest tag..."

    if docker push "$LATEST_IMAGE_NAME"; then
        echo "✅ Successfully pushed latest image on attempt $i"
        break
    else
        echo "⚠️  Push attempt $i failed"
        if [ $i -eq $RETRY_COUNT ]; then
            echo "❌ Push failed for latest image after $RETRY_COUNT attempts."
            echo "🔍 Debugging info:"
            echo "   Image exists locally: $(docker images | grep $IMAGE_NAME | grep latest || echo 'NOT FOUND')"
            echo "   Registry connectivity test:"
            curl -f "http://$REGISTRY/v2/" || echo "Registry not reachable"
            exit 1
        else
            echo "⏳ Waiting 5 seconds before retry..."
            sleep 5
        fi
    fi
done

echo "✅ Successfully built and pushed:"
echo "   📦 ${FULL_IMAGE_NAME}"
echo "   📦 ${LATEST_IMAGE_NAME}"
echo ""
echo "🎉 Build and push completed successfully!"
