import logging
import time
import threading
import queue
import asyncio

class ConnectionManager:
    """
    A class to manage connections to mesh network with automatic reconnection.
    """
    def __init__(self, mesh_client, config, max_retries=5, reconnect_interval=10):
        """
        Initialize the connection manager.

        Args:
            mesh_client: The mesh client instance to manage
            config: Configuration settings
            max_retries: Maximum number of reconnection attempts
            reconnect_interval: Time in seconds between reconnection attempts
        """
        self.mesh_client = mesh_client
        self.config = config
        self.max_retries = max_retries
        self.reconnect_interval = reconnect_interval
        self.retry_count = 0
        self._stop_event = threading.Event()
        self._monitor_thread = None

    def start_monitoring(self):
        """Start the connection monitoring thread"""
        if self._monitor_thread is None or not self._monitor_thread.is_alive():
            self._stop_event.clear()
            self._monitor_thread = threading.Thread(target=self._connection_monitor, daemon=True)
            self._monitor_thread.start()
            logging.info("Connection monitoring started")

    def stop_monitoring(self):
        """Stop the connection monitoring thread"""
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._stop_event.set()
            self._monitor_thread.join(timeout=5.0)
            logging.info("Connection monitoring stopped")

    def reset_connection(self):
        """Reset the connection by disconnecting and then reconnecting"""
        logging.info("Resetting connection...")
        try:
            # Disconnect first if connected
            if self.mesh_client.connected:
                self.mesh_client.disconnect()

            # Small delay to ensure clean disconnect
            time.sleep(2)

            # Reconnect
            success = self.mesh_client.connect()
            if success:
                logging.info("Connection reset successful")
                self.retry_count = 0
                return True
            else:
                logging.error("Connection reset failed")
                return False
        except Exception as e:
            logging.error(f"Error during connection reset: {str(e)}")
            return False

    def force_reconnect(self):
        """Force a reconnection attempt even if the client thinks it's connected"""
        logging.info("Forcing reconnection...")
        try:
            # Always disconnect first
            try:
                self.mesh_client.disconnect()
            except Exception as e:
                logging.warning(f"Ignoring error during forced disconnect: {str(e)}")

            # Small delay to ensure clean disconnect
            time.sleep(2)

            # Reset retry count and attempt reconnection
            self.retry_count = 0
            success = self.mesh_client.connect()

            if success:
                logging.info("Forced reconnection successful")
                return True
            else:
                logging.error("Forced reconnection failed")
                return False
        except Exception as e:
            logging.error(f"Error during forced reconnection: {str(e)}")
            return False

    def _connection_monitor(self):
        """Monitor the connection and reconnect if necessary"""
        while not self._stop_event.is_set():
            if not self.mesh_client.connected and self.retry_count < self.max_retries:
                logging.info(f"Connection lost. Attempting reconnection ({self.retry_count + 1}/{self.max_retries})")
                try:
                    # Try to reconnect
                    success = self.mesh_client.connect()
                    if success:
                        logging.info("Reconnection successful")
                        self.retry_count = 0  # Reset retry count on successful reconnection
                    else:
                        self.retry_count += 1
                        logging.error(f"Reconnection failed. Retry {self.retry_count}/{self.max_retries}")
                except Exception as e:
                    self.retry_count += 1
                    logging.error(f"Error during reconnection: {str(e)}. Retry {self.retry_count}/{self.max_retries}")

                # If max retries reached, notify via Discord
                if self.retry_count >= self.max_retries:
                    logging.critical(f"Maximum reconnection attempts ({self.max_retries}) reached. Giving up.")

                    # Notify via Discord if possible
                    try:
                        if self.mesh_client.discord_client:
                            # Use dictionary format that Discord client can handle
                            error_embed = {
                                "title": "Connection Error",
                                "description": f"Failed to reconnect to Meshtastic device after {self.max_retries} attempts. Manual intervention required.",
                                "color": 0xFF0000  # Red
                            }
                            self.mesh_client.discord_client.enqueue_msg(error_embed)
                    except Exception as e:
                        logging.error(f"Failed to send Discord notification: {str(e)}")

            # Wait before checking again
            for _ in range(self.reconnect_interval * 2):  # Check for stop twice per interval
                if self._stop_event.is_set():
                    break
                time.sleep(0.5)

    def request_reconnect(self):
        """Request an immediate reconnection attempt"""
        self.retry_count = 0  # Reset retry counter for manual reconnect request
        if self._monitor_thread and self._monitor_thread.is_alive():
            logging.info("Manual reconnection requested")
            # Force disconnection to trigger reconnect
            try:
                if self.mesh_client.iface:
                    self.mesh_client.iface.close()
                self.mesh_client.connected = False
            except Exception as e:
                logging.error(f"Error during forced disconnection: {str(e)}")
        else:
            logging.warning("Cannot request reconnection - monitoring not active")
            # Try connecting directly
            self.mesh_client.connect()
