# Use a standard Python image instead of Docker-in-Docker since we're mounting the socket
FROM python:3.11-slim

# Install Docker CLI, Git, and other dependencies
RUN apt-get update && apt-get install -y \
    docker.io \
    git \
    curl \
    ca-certificates \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Create docker CLI plugins directory
RUN mkdir -p /root/.docker/cli-plugins/

# Download and install Docker Buildx plugin
RUN BUILDX_VERSION=$(curl -s https://api.github.com/repos/docker/buildx/releases/latest | grep '"tag_name"' | cut -d'"' -f4) && \
    curl -L "https://github.com/docker/buildx/releases/download/${BUILDX_VERSION}/buildx-${BUILDX_VERSION}.linux-amd64" \
    -o /root/.docker/cli-plugins/docker-buildx && \
    chmod +x /root/.docker/cli-plugins/docker-buildx

# Verify buildx installation
RUN docker buildx version

# Set the working directory inside the container
WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py /app/main.py

# Define the default command to run when the container starts
# This can be overridden when running the container
CMD ["python3", "main.py"]