import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../bot')))
from config_classes import Config

class TestConfigClasses(unittest.TestCase):
    def test_interface_info_serial(self):
        interface_info_dict = {"method": "serial"}
        interface_info = Config.InterfaceInfo(interface_info_dict)

        self.assertEqual(interface_info.interface_type, "serial")
        self.assertEqual(interface_info.connection_descriptor, "serial")
        self.assertIsNone(interface_info.interface_address)
        self.assertIsNone(interface_info.interface_port)
        self.assertIsNone(interface_info.interface_ble_node)

    def test_interface_info_tcp(self):
        interface_info_dict = {
            "method": "tcp",
            "address": "192.168.1.100",
            "port": 4403
        }
        interface_info = Config.InterfaceInfo(interface_info_dict)

        self.assertEqual(interface_info.interface_type, "tcp")
        self.assertEqual(interface_info.interface_address, "192.168.1.100")
        self.assertEqual(interface_info.interface_port, 4403)
        self.assertEqual(interface_info.connection_descriptor, "tcp Address:192.168.1.100 Port:4403")
        self.assertIsNone(interface_info.interface_ble_node)

    def test_interface_info_ble(self):
        interface_info_dict = {
            "method": "ble",
            "ble_node": "MESHTASTIC_83A0"
        }
        interface_info = Config.InterfaceInfo(interface_info_dict)

        self.assertEqual(interface_info.interface_type, "ble")
        self.assertEqual(interface_info.interface_ble_node, "MESHTASTIC_83A0")
        self.assertEqual(interface_info.connection_descriptor, "ble Node:MESHTASTIC_83A0")
        self.assertIsNone(interface_info.interface_address)
        self.assertIsNone(interface_info.interface_port)

    def test_database_info_sqlite(self):
        database_info_dict = {
            "type": "sqlite",
            "db_name": "test.db",
            "db_dir": "test_db"
        }
        database_info = Config.DatabaseInfo(database_info_dict)

        self.assertEqual(database_info.db_type, "sqlite")
        self.assertEqual(database_info.db_name, "test.db")
        self.assertEqual(database_info.db_dir, "test_db")
        self.assertEqual(database_info._db_connection_string, "sqlite:///test_db/test.db")

    def test_database_info_postgres(self):
        database_info_dict = {
            "type": "postgres",
            "host": "localhost",
            "port": "5432",
            "username": "postgres",
            "password": "password",
            "db_name": "test_db"
        }
        database_info = Config.DatabaseInfo(database_info_dict)

        self.assertEqual(database_info.db_type, "postgres")
        self.assertEqual(database_info.db_host, "localhost")
        self.assertEqual(database_info.db_port, "5432")
        self.assertEqual(database_info.db_name, "test_db")
        self.assertEqual(
            database_info._db_connection_string,
            "postgresql+psycopg2://postgres:password@localhost:5432/test_db"
        )

    def test_database_info_unsupported_type(self):
        database_info_dict = {"type": "unsupported"}
        database_info = Config.DatabaseInfo(database_info_dict)

        with self.assertRaises(ValueError):
            _ = database_info._db_connection_string

if __name__ == '__main__':
    unittest.main()
