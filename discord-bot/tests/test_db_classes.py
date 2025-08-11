import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../bot')))
from db_classes import RXPacket, TXPacket, ACK, MeshNodeDB

class TestDatabaseClasses(unittest.TestCase):
    def test_rx_packet_text_message(self):
        rx_packet = RXPacket()
        rx_packet.portnum = 'TEXT_MESSAGE_APP'

        self.assertTrue(rx_packet.is_text_message)

    def test_rx_packet_not_text_message(self):
        rx_packet = RXPacket()
        rx_packet.portnum = 'NODEINFO_APP'

        self.assertFalse(rx_packet.is_text_message)

    def test_rx_packet_src_descriptive(self):
        rx_packet = RXPacket()
        rx_packet.src_id = "!aabbccdd"
        rx_packet.src_short_name = "TestNode"
        rx_packet.src_long_name = "Test Long Name"

        self.assertEqual(rx_packet.src_descriptive, "!aabbccdd | TestNode | Test Long Name")

    @patch('db_classes.meshtastic')
    def test_rx_packet_dst_descriptive_broadcast(self, mock_meshtastic):
        # Setup the mock
        mock_meshtastic.BROADCAST_ADDR = "!broadcast"

        rx_packet = RXPacket()
        rx_packet.dst_id = "!broadcast"

        # Test the function
        self.assertEqual(rx_packet.dst_descriptive, "All Nodes")

if __name__ == '__main__':
    unittest.main()
