# Meshtastic Discord Bot

Originally based on [Kavitate's bot](https://github.com/Kavitate/Meshtastic-Discord-Bot).

## Features

1. Send LoRa messages (to channels or DMs) from discord commands
2. Messages are updated with ACK info
3. Database of all messages received and Nodes
4. List active nodes (in the last X minutes)
5. List all nodes
6. Lookup Ham callsigns
7. Map a specific node's last location
8. Lookup a node's info in the database

## Commands

1. /active: List all active nodes in last 61 minutes
2. /all_nodes: List all nodes in the db
3. /dm: Use to send a direct message to a node (can specify shortname, node ID, or node number)
4. /ham: Lookup ham callsign info
5. /kms: Remotely kill the bot
6. /map: Map a specific node
7. /nodeinfo: Gets node info for a specific node
8. /self: Prints info about host node
9. /YOUR_CHANNEL_1 (etc): Send message on channel

## Discord Configuration

1. In a discord server, create a channel for the bot (commands and responses will be used in this channel)
    1. Get the channel id (instructions [here](https://support.discord.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID))
2. Create a [discord bot](https://discordpy.readthedocs.io/en/stable/discord.html)
3. Update the config.json with your bot token and channel ID

## Installation Options

### Run Locally - Python

1. Clone the repo
2. Run `pip install -r discord-bot/requirements.txt`
3. Run `python discord-bot/bot/main.py`, or in VS Code, run it via the debugger.

### Linux Service

1. Copy the files from `discord-bot/bot` to `/usr/share/mesh-client` on a rpi (or other linux device)
2. Run `pip install -r requirements.txt`
3. Copy mesh-discord.service to `/lib/systemd/system` to register it as a service

### Docker

Out of date, don't use. Check back later, maybe

## Config File

Follow `config_example.json`, rename it `config.json`, remove any comments.

1. the first couple items should be self explanatory (discord_bot_token, discord_channel_id)
2. time_zone requires pztz format ([see here](https://gist.github.com/heyalexej/8bf688fd67d7199be4a1682b3eec7568))
3. Channel Names
    1. These are the names of the channels on your LoRa device
    2. they do not have to match what is on your device
    3. But you must have at least one entry (0)
    4. Delete the ones you don't need
4. Interface Info
    1. Method is the first thing, options are: serial, ble, tcp
    2. serial doesn't require any other interface info items
    3. address and port are used for a tcp connection
    4. ble_node is used for a ble connection - such as `XXXX_83a0`

## Database Info

No docs

If you start getting errors after an update, its probably because we broke the db schema; delete the db file and restart the bot to create a new one.

## Quirks and Notes

We've tested/developed this mainly using serial connections. We know BLE and TCP work, but not a lot of development. We're working on reconnection/disconnection logic. There are some weird behaviors when TCP/BLE connected nodes disconnect.

## Other Notes

1. All commands shall be defined in main.py
2. All messages to discord should be enqueued to the discord_client class defined in discord_client.py (except replies in commands, defined in main.py)
3. All LoRa messages shall be enqueued to the mesh_client classes defined in mesh_client.py
4. An end goal is have everything stored in a DB so we can have 1 database with multiple bots feeding it data
