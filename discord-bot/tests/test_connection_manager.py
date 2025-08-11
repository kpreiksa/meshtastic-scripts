import sys
import os
import unittest
from unittest.mock import patch, MagicMock, call
import time
import threading

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../bot')))
from connection_manager import ConnectionManager

class TestConnectionManager(unittest.TestCase):
    def setUp(self):
        self.mesh_client = MagicMock()
        self.config = MagicMock()
        self.connection_manager = ConnectionManager(
            mesh_client=self.mesh_client,
            config=self.config,
            max_retries=3,
            reconnect_interval=1
        )

    def test_start_monitoring(self):
        """Test starting the connection monitoring thread"""
        self.connection_manager.start_monitoring()
        self.assertIsNotNone(self.connection_manager._monitor_thread)
        self.assertTrue(self.connection_manager._monitor_thread.is_alive())

        # Clean up
        self.connection_manager.stop_monitoring()

    def test_stop_monitoring(self):
        """Test stopping the connection monitoring thread"""
        self.connection_manager.start_monitoring()
        self.assertTrue(self.connection_manager._monitor_thread.is_alive())

        self.connection_manager.stop_monitoring()
        time.sleep(0.1)  # Give thread time to stop
        self.assertFalse(self.connection_manager._monitor_thread.is_alive())

    def test_reset_connection(self):
        """Test the reset_connection method"""
        # Mock the mesh_client.connected property
        type(self.mesh_client).connected = MagicMock(return_value=True)
        self.mesh_client.connect.return_value = True

        result = self.connection_manager.reset_connection()

        self.assertTrue(result)
        self.mesh_client.disconnect.assert_called_once()
        self.mesh_client.connect.assert_called_once()
        self.assertEqual(self.connection_manager.retry_count, 0)

    def test_reset_connection_failure(self):
        """Test reset_connection when reconnection fails"""
        # Mock the mesh_client.connected property
        type(self.mesh_client).connected = MagicMock(return_value=True)
        self.mesh_client.connect.return_value = False

        result = self.connection_manager.reset_connection()

        self.assertFalse(result)
        self.mesh_client.disconnect.assert_called_once()
        self.mesh_client.connect.assert_called_once()

    def test_force_reconnect(self):
        """Test the force_reconnect method"""
        self.mesh_client.connect.return_value = True

        result = self.connection_manager.force_reconnect()

        self.assertTrue(result)
        self.mesh_client.disconnect.assert_called_once()
        self.mesh_client.connect.assert_called_once()
        self.assertEqual(self.connection_manager.retry_count, 0)

    def test_connection_monitor_reconnects(self):
        """Test that connection monitor attempts to reconnect when disconnected"""
        # Set up mesh_client to be disconnected initially, then connect on attempt
        self.connection_manager.retry_count = 0
        type(self.mesh_client).connected = MagicMock(side_effect=[False, True, True])
        self.mesh_client.connect.return_value = True

        # Start monitoring in a separate thread so we can control its lifetime
        monitor_thread = threading.Thread(
            target=self.connection_manager._connection_monitor,
            daemon=True
        )
        monitor_thread.start()

        # Give the thread time to attempt reconnection
        time.sleep(2)

        # Stop the thread
        self.connection_manager._stop_event.set()
        monitor_thread.join(timeout=1.0)

        # Verify reconnection was attempted
        self.mesh_client.connect.assert_called()
        self.assertEqual(self.connection_manager.retry_count, 0)  # Should reset after successful connection

    def test_connection_monitor_max_retries(self):
        """Test that connection monitor stops after max retries"""
        # Set up mesh_client to always fail reconnection
        self.connection_manager.retry_count = 0
        type(self.mesh_client).connected = MagicMock(return_value=False)
        self.mesh_client.connect.return_value = False

        # Start monitoring in a separate thread so we can control its lifetime
        monitor_thread = threading.Thread(
            target=self.connection_manager._connection_monitor,
            daemon=True
        )
        monitor_thread.start()

        # Give the thread time to attempt max_retries reconnections
        time.sleep(4)

        # Stop the thread
        self.connection_manager._stop_event.set()
        monitor_thread.join(timeout=1.0)

        # Verify reconnection was attempted max_retries times
        self.assertEqual(self.mesh_client.connect.call_count, 3)  # max_retries = 3
        self.assertEqual(self.connection_manager.retry_count, 3)

        # Verify Discord notification was attempted
        self.mesh_client.discord_client.enqueue_msg.assert_called()

if __name__ == '__main__':
    unittest.main()
