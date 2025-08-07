#!/bin/bash

#need to chmod +x this file, and then sudo ./setup_discordbot.sh
#finally make sure your config is updated & and the correct path

# # Exit immediately if a command exits with a non-zero status
# set -e
# set -x

SERVICE_NAME="mesh-discord.service"

if systemctl list-units --type=service --all | grep -q "$SERVICE_NAME"; then
    echo "Stopping $SERVICE_NAME..."
    sudo systemctl stop "$SERVICE_NAME"
else
    echo "$SERVICE_NAME not found, skipping stop."
fi

# Remove the repo directory if it exists
if [ -d "meshtastic-scripts" ]; then
    echo "Removing existing directory: meshtastic-scripts"
    rm -rf meshtastic-scripts
fi


# Clone the repository
git clone https://github.com/kpreiksa/meshtastic-scripts.git
cd meshtastic-scripts
# git checkout refactor
cd discord-bot|| { echo "Failed to cd into discord-bot"; exit 1; }


# Create the target directory
sudo mkdir -p /usr/share/mesh-client/

echo "Current directory: $(pwd)"

# Copy contents from /meshtastic-scripts to /usr/share/mesh-client
sudo cp -a . /usr/share/mesh-client/

# Navigate to the directory
cd /usr/share/mesh-client/ || { echo "Failed to cd into /usr/share/mesh-client/"; exit 1; }

# Make mesh-service-script.sh executable
chmod +x mesh-service-script.sh

# Create and activate Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# read -p "Paused. Press Enter to continue..."
# Copy service file to systemd directory
echo "copying mesh-discord.service to /lib/systemd/system"
sudo cp mesh-discord.service /lib/systemd/system/
echo "enabling mesh-discord.service"
sudo systemctl enable mesh-discord.service
echo "starting mesh-discord.service"
sudo systemctl start mesh-discord.service

SERVICE_NAME="mesh-discord.service"
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "$SERVICE_NAME is running."
else
    echo "$SERVICE_NAME is NOT running :("
fi

echo "setup process complete!"
echo ""
echo "You will likely need to add/modify your config file located in /usr/share/mesh-client/config to include your Discord token, meshtastic channels & keys, and the method your node will use to communicate with bot/n/nPress enter to continue"
