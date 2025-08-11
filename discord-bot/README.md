# Meshtastic Discord Bot

Originally based on [Kavitate's bot](https://github.com/Kavitate/Meshtastic-Discord-Bot).

Source code for the bot is located in `./discord-bot/bot`. Additional files for docker, configuration, db scripts, and docker compose are in the `./discord-bot` directory.

## Features

1. Send LoRa messages (to channels or DMs) from discord commands
2. Messages are updated with ACK info
3. Database of all messages received and Nodes
4. List active nodes (in the last X minutes)
5. List all nodes
6. Lookup Ham callsigns
7. Map a specific node's last location
8. Lookup a node's info in the database
9. Automatic reconnection to mesh network when connection is lost
10. Improved database handling with connection pooling and error handling

## Bot Commands

1. `/active`: List all active nodes in last 61 minutes
2. `/all_nodes`: List all nodes in the db
3. `/dm`: Use to send a direct message to a node (can specify shortname, node ID, or node number)
4. `/ham`: Lookup ham callsign info
5. `/kms`: Remotely kill the bot
6. `/map`: Map a specific node
7. `/nodeinfo`: Gets node info for a specific node
8. `/self`: Prints info about host node
9. `/reconnect`: Force reconnection to the mesh network
10. `/YOUR_CHANNEL_1` (etc): Send message on channel

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

This repo includes options to run the database, grafana dashboard, and bot in a docker-compose environment, as well as building the bot image and pushing it to a local registry. This is not required.

#### Docker Files

- **Dockerfile** - File for creating the image
- **docker-build-and-push.sh** - Script to build and push the image to a local registry
- **docker-config_example.env** - Example config file, rename to docker-config.env and update with your registry info

#### Docker Compose Files

These files are for setting up the database, grafana, and the bot in a docker-compose environment. You must still use the other [Docker Files](#docker-files) to build the bot image and get it to your registry. Hosting a registry is not required, but it makes it easier to manage the bot image.

The docker-compose.yaml now includes:
- Health checks for all services
- Automatic restarts for the bot on failure
- Proper service dependency management

## Bot Config File

Follow `config_example.json`, rename it `config.json`, remove any comments.

1. Discord configuration:
   - `discord_bot_token`: Your Discord bot token
   - `discord_channel_id`: Channel ID where the bot will operate
2. Time zone:
   - `time_zone`: Uses pytz format ([see here](https://gist.github.com/heyalexej/8bf688fd67d7199be4a1682b3eec7568))
3. Channel Names:
   - These are the names of the channels on your LoRa device
   - They do not have to match what is on your device
   - You must have at least one entry (0)
   - Delete the ones you don't need
4. Interface Info:
   - Method is the first thing, options are: `serial`, `ble`, `tcp`
   - `serial` doesn't require any other interface info items
   - `address` and `port` are used for a tcp connection
   - `ble_node` is used for a ble connection - such as `XXXX_83a0`
5. Database configuration:
   - `type`: Database type (sqlite or postgres/postgresql)
   - For SQLite: `db_name` and `db_dir`
   - For PostgreSQL: `host`, `port`, `username`, `password`, `db_name`

Instead of using a config file, you can also set environment variables. The bot will look for these variables. These are documented in `config_example.env`.

## Database Management

The bot now includes a `DatabaseClient` class that provides a cleaner interface for database operations with proper connection pooling and error handling. This improves reliability and makes database interactions more robust.

### Automatic Database Migrations

The database schema is automatically created on first run. If you encounter errors after an update, it's likely due to schema changes. You can either:

1. Delete the database file (for SQLite) and let the bot recreate it
2. Use the database migration scripts in `db_scripts` directory to upgrade your existing database

For PostgreSQL users, the migration scripts in `db_scripts` folder provide a way to safely upgrade your database schema.

### Connection Management

The bot now features a robust connection management system that:

1. Automatically attempts to reconnect to the mesh network if the connection is lost
2. Provides a `/reconnect` command to force reconnection if needed
3. Reports connection status through Discord messages
4. Handles various connection types (Serial, TCP, BLE) with appropriate error handling

This significantly improves reliability, especially for TCP and BLE connections which were previously prone to disconnection issues.

The bot now includes a database migration system. You can use the `db_scripts/update_db.py` script to automatically update your database schema:

```bash
python db_scripts/update_db.py
```

This will:
1. Detect your current database version
2. Find and apply the appropriate update scripts
3. Track schema version in the database

To create a dry-run without making changes:
```bash
python db_scripts/update_db.py --dry-run
```

## Testing

Unit tests are available in the `tests` directory. To run the tests:

```bash
pytest -v tests/
```

## Troubleshooting

### Connection Issues
The bot now includes automatic reconnection logic that will:
1. Detect when connection to the mesh network is lost
2. Attempt to reconnect multiple times with increasing delays
3. Notify in Discord when connection issues occur

### Database Errors
If you encounter database errors, you can:
1. Run the database update script to ensure your schema is up to date
2. Check the logs for specific error messages
3. For SQLite: ensure the database directory is writable
4. For PostgreSQL: verify connection credentials and database existence

## Other Notes

1. All commands shall be defined in main.py
2. All messages to discord should be enqueued to the discord_client class defined in discord_client.py (except replies in commands, defined in main.py)
3. All LoRa messages shall be enqueued to the mesh_client classes defined in mesh_client.py
4. We now have a DatabaseClient class in db_client.py that handles all database interactions and error handling
