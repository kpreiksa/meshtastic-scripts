#!/usr/bin/env python3
"""
Database Schema Update Script

This script automatically determines the current database schema version and
applies the appropriate update scripts to bring the database to the latest version.

Usage:
    python update_db.py [--db-type TYPE] [--db-path PATH] [--host HOST] [--port PORT]
                       [--username USER] [--password PASS] [--db-name NAME]
                       [--scripts-dir DIR] [--dry-run]

Options:
    --db-type TYPE      Database type (sqlite or postgres)
    --db-path PATH      Path to SQLite database file
    --host HOST         PostgreSQL host
    --port PORT         PostgreSQL port
    --username USER     PostgreSQL username
    --password PASS     PostgreSQL password
    --db-name NAME      PostgreSQL database name
    --scripts-dir DIR   Directory containing update scripts
    --dry-run           Print updates that would be applied without making changes
"""

import os
import sys
import argparse
import logging
import glob
import re
import importlib.util
from sqlalchemy import create_engine, Column, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text
from sqlalchemy.exc import SQLAlchemyError, ProgrammingError

# Add parent directory to path so we can import config_classes
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from bot.config_classes import Config
except ImportError:
    print("Could not import Config class. Make sure the bot directory is accessible.")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)

Base = declarative_base()

class SchemaVersion(Base):
    """Table to track database schema version"""
    __tablename__ = 'schema_version'

    version = Column(String(20), primary_key=True)
    applied_date = Column(String(30))

def get_connection_string(args):
    """Build a database connection string from arguments or config"""
    if args.db_type:
        db_type = args.db_type
    else:
        config = Config()
        db_type = config.database_info.db_type

    if db_type == 'sqlite':
        if args.db_path:
            return f"sqlite:///{args.db_path}"
        else:
            config = Config()
            db_dir = config.database_info.db_dir
            db_name = config.database_info.db_name
            return f"sqlite:///{db_dir}/{db_name}"
    elif db_type in ('postgres', 'postgresql'):
        host = args.host or Config().database_info.db_host
        port = args.port or Config().database_info.db_port
        username = args.username or Config().database_info._db_username
        password = args.password or Config().database_info._db_password
        db_name = args.db_name or Config().database_info.db_name
        return f"postgresql+psycopg2://{username}:{password}@{host}:{port}/{db_name}"
    else:
        raise ValueError(f"Unsupported database type: {db_type}")

def get_scripts_dir(args):
    """Determine the directory containing update scripts"""
    if args.scripts_dir:
        return args.scripts_dir
    else:
        # Default to db_scripts directory
        return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'db_scripts'))

def get_current_version(engine):
    """Get the current database schema version"""
    try:
        # Try to create schema_version table if it doesn't exist
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        # Get the current version
        version_record = session.query(SchemaVersion).order_by(SchemaVersion.version.desc()).first()
        session.close()

        if version_record:
            return version_record.version
        else:
            # No version record, assume 0.0.0
            return "0.0.0"
    except SQLAlchemyError as e:
        logging.error(f"Error getting current schema version: {e}")
        return None

def get_update_scripts(scripts_dir, current_version):
    """
    Find all update scripts with versions higher than the current version.
    Returns a sorted list of (version, script_path) tuples.
    """
    all_scripts = []

    # Find all update directories
    version_dirs = [d for d in os.listdir(scripts_dir) if os.path.isdir(os.path.join(scripts_dir, d))]

    for version_dir in version_dirs:
        update_dir = os.path.join(scripts_dir, version_dir, 'update')
        if os.path.isdir(update_dir):
            # Find all SQL files in this update directory
            sql_files = glob.glob(os.path.join(update_dir, 'from_*.sql'))

            for sql_file in sql_files:
                # Extract the from_version from the filename
                from_version_match = re.search(r'from_([0-9.]+)\.sql', os.path.basename(sql_file))
                if from_version_match:
                    from_version = from_version_match.group(1)
                    to_version = version_dir

                    # Only include scripts that update from our current version or higher
                    if from_version == current_version:
                        all_scripts.append((to_version, sql_file, from_version))

    # Sort scripts by target version
    return sorted(all_scripts, key=lambda x: [int(p) for p in x[0].split('.')])

def apply_update_script(engine, script_path, from_version, to_version, dry_run=False):
    """Apply a single update script to the database"""
    logging.info(f"Applying update from {from_version} to {to_version}")

    if dry_run:
        logging.info(f"DRY RUN: Would apply {script_path}")
        return True

    try:
        # Read the script
        with open(script_path, 'r') as f:
            script_content = f.read()

        # Execute the script
        connection = engine.connect()
        transaction = connection.begin()

        try:
            # Split the script into individual statements (assuming they're separated by semicolons)
            statements = script_content.split(';')
            for statement in statements:
                if statement.strip():
                    connection.execute(text(statement))

            # Update the version
            connection.execute(text(
                "INSERT INTO schema_version (version, applied_date) VALUES (:version, datetime('now'))"
            ), {"version": to_version})

            transaction.commit()
            logging.info(f"Successfully updated to version {to_version}")
            return True

        except SQLAlchemyError as e:
            transaction.rollback()
            logging.error(f"Error applying update script: {e}")
            return False
        finally:
            connection.close()

    except Exception as e:
        logging.error(f"Error reading or executing update script: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Database Schema Update Tool")
    parser.add_argument('--db-type', help='Database type (sqlite or postgres)')
    parser.add_argument('--db-path', help='Path to SQLite database file')
    parser.add_argument('--host', help='PostgreSQL host')
    parser.add_argument('--port', help='PostgreSQL port')
    parser.add_argument('--username', help='PostgreSQL username')
    parser.add_argument('--password', help='PostgreSQL password')
    parser.add_argument('--db-name', help='PostgreSQL database name')
    parser.add_argument('--scripts-dir', help='Directory containing update scripts')
    parser.add_argument('--dry-run', action='store_true', help='Print updates that would be applied without making changes')

    args = parser.parse_args()

    # Get connection string
    try:
        connection_string = get_connection_string(args)
        scripts_dir = get_scripts_dir(args)

        logging.info(f"Using scripts directory: {scripts_dir}")
        logging.info(f"Connecting to database...")

        # Connect to database
        engine = create_engine(connection_string)

        # Get current version
        current_version = get_current_version(engine)
        if not current_version:
            logging.error("Could not determine current database version.")
            return 1

        logging.info(f"Current database schema version: {current_version}")

        # Find applicable update scripts
        update_scripts = get_update_scripts(scripts_dir, current_version)

        if not update_scripts:
            logging.info("Database is already at the latest version.")
            return 0

        logging.info(f"Found {len(update_scripts)} update scripts to apply")

        # Apply each update script in order
        for to_version, script_path, from_version in update_scripts:
            success = apply_update_script(
                engine, script_path, from_version, to_version, dry_run=args.dry_run
            )
            if not success:
                logging.error(f"Failed to update to version {to_version}. Stopping.")
                return 1

            # Update current version for the next iteration
            current_version = to_version

        logging.info(f"Database updated to version {current_version}")
        return 0

    except Exception as e:
        logging.error(f"Error: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
