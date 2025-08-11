#!/usr/bin/env python
"""
Database migration helper script to automate migration process.
"""

import os
import sys
import argparse
import logging
import re
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))
from bot.db_client import DatabaseClient
from bot.config_classes import Config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

def get_current_version(db_client):
    """
    Get the current database version from the version table.
    Creates the version table if it doesn't exist.
    """
    session = db_client.get_session()

    try:
        # Check if version table exists
        result = session.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'db_version')")
        if not result.scalar():
            # Create version table if it doesn't exist
            session.execute("CREATE TABLE IF NOT EXISTS db_version (version VARCHAR(20) NOT NULL, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
            session.execute("INSERT INTO db_version (version) VALUES ('0.0.9')")  # Starting version
            session.commit()
            return "0.0.9"

        # Get current version
        result = session.execute("SELECT version FROM db_version ORDER BY updated_at DESC LIMIT 1")
        version = result.scalar()
        return version
    except Exception as e:
        logging.error(f"Error getting database version: {e}")
        return None
    finally:
        session.close()

def get_available_migrations(base_dir, current_version):
    """
    Get available migration scripts for upgrading from current version.
    """
    migrations = []
    pattern = re.compile(r'from_([0-9]+\.[0-9]+\.[0-9]+)\.sql')

    for file in os.listdir(base_dir):
        match = pattern.match(file)
        if match and match.group(1) == current_version:
            migrations.append(os.path.join(base_dir, file))

    return migrations

def apply_migration(db_client, migration_file):
    """
    Apply a migration script to the database.
    """
    # Extract target version from filename
    match = re.search(r'to_([0-9]+\.[0-9]+\.[0-9]+)\.sql', migration_file)
    if not match:
        logging.error(f"Could not determine target version from filename: {migration_file}")
        return False

    target_version = match.group(1)

    # Read migration SQL
    with open(migration_file, 'r') as f:
        migration_sql = f.read()

    session = db_client.get_session()
    try:
        # Execute migration script
        for statement in migration_sql.split(';'):
            statement = statement.strip()
            if statement:
                session.execute(statement)

        # Update version in db_version table
        session.execute(f"INSERT INTO db_version (version) VALUES ('{target_version}')")
        session.commit()

        logging.info(f"Successfully migrated database to version {target_version}")
        return True
    except Exception as e:
        session.rollback()
        logging.error(f"Error applying migration: {e}")
        return False
    finally:
        session.close()

def main():
    parser = argparse.ArgumentParser(description="Database migration helper script")
    parser.add_argument('--check', action='store_true', help='Check current database version')
    parser.add_argument('--migrate', action='store_true', help='Run database migration')
    parser.add_argument('--config', type=str, help='Path to config file', default='config.json')

    args = parser.parse_args()

    # Load config
    config = Config(args.config)
    db_info = config.database_info

    # Initialize database client
    db_client = DatabaseClient(db_info._db_connection_string)

    if args.check:
        current_version = get_current_version(db_client)
        if current_version:
            logging.info(f"Current database version: {current_version}")
        else:
            logging.error("Could not determine current database version.")

    if args.migrate:
        current_version = get_current_version(db_client)
        if not current_version:
            logging.error("Could not determine current database version for migration.")
            return

        logging.info(f"Current database version: {current_version}")

        # Get migration directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        db_scripts_dir = os.path.abspath(os.path.join(script_dir, '../..'))
        update_dir = os.path.join(db_scripts_dir, '0.1', 'update')

        # Get available migrations
        migrations = get_available_migrations(update_dir, current_version)

        if not migrations:
            logging.info(f"No migrations available for version {current_version}")
            return

        # Apply migrations
        for migration in migrations:
            logging.info(f"Applying migration: {os.path.basename(migration)}")
            success = apply_migration(db_client, migration)
            if not success:
                logging.error("Migration failed.")
                return

        logging.info("All migrations completed successfully.")

    # Close database client
    db_client.close()

if __name__ == "__main__":
    main()
