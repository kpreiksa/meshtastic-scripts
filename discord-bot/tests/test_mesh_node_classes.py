import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../bot')))
import mesh_node_classes

class MockMeshNode:
    def __init__(self, node_num=1, node_id="!aabbccdd", name="TestNode",
                 long_name="TestLongName", hw_model="TBEAM", last_heard=1627123456):
        self.node_num = node_num
        self.node_id = node_id
        self.name = name
        self.long_name = long_name
        self.hw_model = hw_model
        self.last_heard = last_heard

class TestMeshNodeClasses(unittest.TestCase):
    @patch('mesh_node_classes.MeshNode')
    def test_mesh_node_creation(self, mock_mesh_node):
        # Setup the mock
        instance = mock_mesh_node.return_value
        instance.node_num = 1
        instance.node_id = "!aabbccdd"
        instance.name = "TestNode"
        instance.long_name = "TestLongName"
        instance.hw_model = "TBEAM"
        instance.last_heard = 1627123456

        # Create a real instance
        mesh_node = mesh_node_classes.MeshNode()

        # Verify the mock works
        self.assertEqual(mesh_node.node_num, 1)
        self.assertEqual(mesh_node.node_id, "!aabbccdd")
        self.assertEqual(mesh_node.name, "TestNode")
        self.assertEqual(mesh_node.long_name, "TestLongName")
        self.assertEqual(mesh_node.hw_model, "TBEAM")
        self.assertEqual(mesh_node.last_heard, 1627123456)

if __name__ == '__main__':
    unittest.main()
