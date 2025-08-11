#!/usr/bin/env python
"""
Meshtastic Discord Bot Database Update Helper

This script helps update your database schema when upgrading the bot.
It reads the current database version and applies the appropriate migration scripts.
"""

import os
import sys
import argparse
import sqlite3
import psycopg2
import re
from pathlib import Path

def get_current_db_version_sqlite(db_path):
    """Get the current database version from SQLite"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Try to get version from version table (newer method)
        try:
            cursor.execute("SELECT version FROM db_version ORDER BY id DESC LIMIT 1")
            result = cursor.fetchone()
            if result:
                return result[0]
        except sqlite3.OperationalError:
            pass

        # If no version table, try to infer from schema
        tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = [t[0] for t in tables]

        if "connection_state" in table_names:
            return "0.1.0"
        elif "mesh_nodes" in table_names:
            return "0.0.9"
        else:
            return "unknown"
    except Exception as e:
        print(f"Error getting SQLite database version: {e}")
        return None
    finally:
        conn.close()

def get_current_db_version_postgres(host, port, dbname, user, password):
    """Get the current database version from PostgreSQL"""
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password
        )
        cursor = conn.cursor()

        # Try to get version from version table (newer method)
        try:
            cursor.execute("SELECT version FROM db_version ORDER BY id DESC LIMIT 1")
            result = cursor.fetchone()
            if result:
                return result[0]
        except psycopg2.errors.UndefinedTable:
            pass

        # If no version table, try to infer from schema
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        table_names = [t[0] for t in cursor.fetchall()]

        if "connection_state" in table_names:
            return "0.1.0"
        elif "mesh_nodes" in table_names:
            return "0.0.9"
        else:
            return "unknown"
    except Exception as e:
        print(f"Error getting PostgreSQL database version: {e}")
        return None
    finally:
        conn.close()

def apply_migration_sqlite(db_path, migration_file):
    """Apply a migration SQL file to SQLite database"""
    try:
        print(f"Applying migration {os.path.basename(migration_file)} to SQLite database...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        with open(migration_file, 'r') as f:
            sql_script = f.read()

        # SQLite doesn't support some PostgreSQL syntax, so we need to adapt
        sql_script = sql_script.replace('SERIAL PRIMARY KEY', 'INTEGER PRIMARY KEY AUTOINCREMENT')
        sql_script = re.sub(r'CREATE INDEX IF NOT EXISTS ([a-zA-Z0-9_]+)', 'CREATE INDEX \\1', sql_script)

        # Remove PostgreSQL-specific commands
        sql_script = re.sub(r'ALTER TABLE [a-zA-Z0-9_]+ ADD COLUMN IF NOT EXISTS', 'ALTER TABLE', sql_script)

        # Split by semicolon to execute each statement separately
        statements = sql_script.split(';')
        for statement in statements:
            if statement.strip():
                try:
                    cursor.execute(statement)
                except sqlite3.OperationalError as e:
                    print(f"Warning: {e}")
                    # Continue with next statement

        conn.commit()
        print("Migration applied successfully!")
        return True
    except Exception as e:
        print(f"Error applying migration to SQLite: {e}")
        return False
    finally:
        conn.close()

def apply_migration_postgres(host, port, dbname, user, password, migration_file):
    """Apply a migration SQL file to PostgreSQL database"""
    try:
        print(f"Applying migration {os.path.basename(migration_file)} to PostgreSQL database...")
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password
        )
        cursor = conn.cursor()

        with open(migration_file, 'r') as f:
            sql_script = f.read()

        # Execute the script
        cursor.execute(sql_script)
        conn.commit()
        print("Migration applied successfully!")
        return True
    except Exception as e:
        print(f"Error applying migration to PostgreSQL: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def get_migration_files(script_dir, from_version, to_version):
    """Get the list of migration files to apply"""
    # Ensure script_dir is a Path object
    script_dir = Path(script_dir) if not isinstance(script_dir, Path) else script_dir

    update_dir = script_dir / "update"
    if not update_dir.exists():
        print(f"Update directory not found: {update_dir}")
        return []

    # Find migration files for the target upgrade
    migration_pattern = f"from_{from_version.replace('.', '_')}_to_{to_version.replace('.', '_')}.sql"
    migration_files = list(update_dir.glob(migration_pattern))

    if not migration_files:
        print(f"No migration file found for upgrading from {from_version} to {to_version}")
        return []

    return [str(f) for f in migration_files]

def main():
    parser = argparse.ArgumentParser(description='Meshtastic Discord Bot Database Update Helper')
    parser.add_argument('--db-type', choices=['sqlite', 'postgres'], required=True, help='Database type')
    parser.add_argument('--db-path', help='Path to SQLite database file')
    parser.add_argument('--db-host', help='PostgreSQL host')
    parser.add_argument('--db-port', default='5432', help='PostgreSQL port')
    parser.add_argument('--db-name', help='PostgreSQL database name')
    parser.add_argument('--db-user', help='PostgreSQL username')
    parser.add_argument('--db-password', help='PostgreSQL password')
    parser.add_argument('--script-dir', default='db_scripts', help='Directory containing migration scripts')
    parser.add_argument('--target-version', default='0.2.0', help='Target version to upgrade to')

    args = parser.parse_args()

    # Validate arguments
    if args.db_type == 'sqlite' and not args.db_path:
        print("Error: --db-path is required for SQLite")
        return 1

    if args.db_type == 'postgres' and (not args.db_host or not args.db_name or not args.db_user or not args.db_password):
        print("Error: --db-host, --db-name, --db-user, and --db-password are required for PostgreSQL")
        return 1

    # Get current database version
    if args.db_type == 'sqlite':
        current_version = get_current_db_version_sqlite(args.db_path)
    else:
        current_version = get_current_db_version_postgres(
            args.db_host, args.db_port, args.db_name, args.db_user, args.db_password
        )

    if not current_version:
        print("Error: Could not determine current database version")
        return 1

    print(f"Current database version: {current_version}")
    print(f"Target database version: {args.target_version}")

    if current_version == args.target_version:
        print("Database is already at the target version, nothing to do")
        return 0

    # Get migration files
    migration_files = get_migration_files(args.script_dir, current_version, args.target_version)

    if not migration_files:
        print("No migration files found, cannot update database")
        return 1

    # Apply migrations
    success = True
    for migration_file in migration_files:
        if args.db_type == 'sqlite':
            success = apply_migration_sqlite(args.db_path, migration_file)
        else:
            success = apply_migration_postgres(
                args.db_host, args.db_port, args.db_name, args.db_user, args.db_password, migration_file
            )

        if not success:
            break

    if success:
        print(f"Successfully updated database from version {current_version} to {args.target_version}")
        return 0
    else:
        print("Failed to update database")
        return 1

if __name__ == "__main__":
    sys.exit(main())
