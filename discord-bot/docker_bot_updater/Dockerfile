# Use a standard Python image instead of Docker-in-Docker since we're mounting the socket
FROM python:3.11-slim

# Install Docker CLI, Git, and other dependencies
RUN apt-get update && apt-get install -y \
    docker.io \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory inside the container
WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py /app/main.py

# Define the default command to run when the container starts
# This can be overridden when running the container
CMD ["python3", "main.py"]