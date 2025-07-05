# Use a base image with Python
FROM python:3.11-slim

# Install required system packages
RUN apt-get update && apt-get install -y \
    bluetooth \
    bluez \
    bluez-tools \
    libbluetooth-dev \
    python3-dev \
    dbus \
    gcc \
    vim \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory inside the container
WORKDIR /app

# Copy your application files into the container
COPY main.py /app/main.py
COPY config.json /app/config.json
COPY requirements.txt /app/requirements.txt

# Install any dependencies (if applicable)
RUN pip install -r requirements.txt


# Define the command to run when the container starts
# technically `bluetoothctl list` isn't necessary, but its nice for debugging purposes
# In my testing, there was a race condition between the python script and the bluetooth adapter being available, hence the 5s. Seems no issue
CMD ["bash", "-c", "bluetoothctl list && sleep 5 && python3 main.py"]
