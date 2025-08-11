#!/usr/bin/env python
"""
Database Connectivity Test

This script tests connectivity to both SQLite and PostgreSQL databases
and reports any issues found. It's useful for troubleshooting database
connection problems.
"""

import os
import sys
import argparse
import sqlite3
import psycopg2

def test_sqlite_connection(db_path):
    """Test connection to a SQLite database"""
    print(f"Testing SQLite database at: {db_path}")

    if not os.path.exists(db_path):
        print(f"ERROR: Database file does not exist at {db_path}")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Test if we can execute queries
        cursor.execute("SELECT sqlite_version();")
        version = cursor.fetchone()[0]
        print(f"SQLite version: {version}")

        # Try to get a list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        print(f"Found {len(tables)} tables in the database:")
        for table in tables:
            print(f"  - {table[0]}")

        conn.close()
        print("Connection test successful!")
        return True
    except Exception as e:
        print(f"ERROR: Failed to connect to SQLite database: {e}")
        return False

def test_postgres_connection(host, port, dbname, user, password):
    """Test connection to a PostgreSQL database"""
    print(f"Testing PostgreSQL database at: {host}:{port}/{dbname}")

    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password
        )
        cursor = conn.cursor()

        # Test if we can execute queries
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"PostgreSQL version: {version}")

        # Try to get a list of tables
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
        tables = cursor.fetchall()

        print(f"Found {len(tables)} tables in the database:")
        for table in tables:
            print(f"  - {table[0]}")

        conn.close()
        print("Connection test successful!")
        return True
    except Exception as e:
        print(f"ERROR: Failed to connect to PostgreSQL database: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Test database connectivity')
    parser.add_argument('--db-type', choices=['sqlite', 'postgres'], required=True, help='Database type')
    parser.add_argument('--db-path', help='Path to SQLite database file')
    parser.add_argument('--db-host', help='PostgreSQL host')
    parser.add_argument('--db-port', default='5432', help='PostgreSQL port')
    parser.add_argument('--db-name', help='PostgreSQL database name')
    parser.add_argument('--db-user', help='PostgreSQL username')
    parser.add_argument('--db-password', help='PostgreSQL password')

    args = parser.parse_args()

    # Validate arguments
    if args.db_type == 'sqlite' and not args.db_path:
        print("Error: --db-path is required for SQLite")
        return 1

    if args.db_type == 'postgres' and (not args.db_host or not args.db_name or not args.db_user or not args.db_password):
        print("Error: --db-host, --db-name, --db-user, and --db-password are required for PostgreSQL")
        return 1

    # Test connection
    success = False
    if args.db_type == 'sqlite':
        success = test_sqlite_connection(args.db_path)
    else:
        success = test_postgres_connection(
            args.db_host, args.db_port, args.db_name, args.db_user, args.db_password
        )

    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
