"""Unit tests for Stage 3 — Code Graph Query (graph_query.py).

Tests cover:
  - Existing node with outgoing neighbors
  - Existing node with incoming neighbors
  - direction="both"
  - direction="incoming"
  - direction="outgoing"
  - Node with no neighbors
  - Unknown node ID
  - Invalid direction
  - Returned metadata correctness
  - Deterministic ordering
  - Querying the existing mini_shop graph
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from mini_swe_agent.graph import CodeGraphBuilder, get_code_neighbors

class TestGraphQuery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Build the graph on the real sandbox for integration tests."""
        cls.sandbox = str(Path(__file__).parent.parent / "sandbox" / "mini_shop")
        builder = CodeGraphBuilder(cls.sandbox)
        cls.graph = builder.build()

    def test_outgoing_neighbors(self):
        # A method that calls another method/function will have outgoing edges
        res = get_code_neighbors(self.graph, "shop/cart.py::ShoppingCart::total_with_discount", direction="outgoing")
        self.assertTrue(len(res) > 0)

        # Verify outgoing structure
        for neighbor in res:
            self.assertEqual(neighbor["direction"], "outgoing")
            self.assertIn("relationship", neighbor)
            self.assertIn("neighbor_id", neighbor)

    def test_incoming_neighbors(self):
        # A method inside a class has incoming 'contains' edge from class
        res = get_code_neighbors(self.graph, "shop/cart.py::ShoppingCart::remove_item", direction="incoming")
        self.assertTrue(len(res) > 0)

        # Verify incoming structure
        for neighbor in res:
            self.assertEqual(neighbor["direction"], "incoming")
            self.assertIn("relationship", neighbor)
            self.assertIn("neighbor_id", neighbor)

    def test_direction_both(self):
        # ShoppingCart class contains methods (outgoing) and is contained by module (incoming)
        res = get_code_neighbors(self.graph, "shop/cart.py::ShoppingCart", direction="both")

        has_incoming = any(n["direction"] == "incoming" for n in res)
        has_outgoing = any(n["direction"] == "outgoing" for n in res)

        self.assertTrue(has_incoming, "Expected at least one incoming edge for class node")
        self.assertTrue(has_outgoing, "Expected at least one outgoing edge for class node")

    def test_node_with_no_neighbors(self):
        # Create an isolated node
        self.graph.graph.add_node("isolated_node")
        res = get_code_neighbors(self.graph, "isolated_node")
        self.assertEqual(res, [])
        self.graph.graph.remove_node("isolated_node")

    def test_unknown_node_id(self):
        # Should return empty list, not crash
        res = get_code_neighbors(self.graph, "does_not_exist_at_all::nonexistent")
        self.assertEqual(res, [])

    def test_invalid_direction(self):
        with self.assertRaises(ValueError):
            get_code_neighbors(self.graph, "shop/cart.py", direction="invalid_dir")

    def test_returned_metadata_correctness(self):
        res = get_code_neighbors(self.graph, "shop/cart.py::ShoppingCart", direction="outgoing")
        # Find the remove_item child
        remove_item_node = next((n for n in res if "remove_item" in n["neighbor_id"]), None)
        self.assertIsNotNone(remove_item_node)

        # Check metadata
        self.assertEqual(remove_item_node["relationship"], "contains")
        self.assertEqual(remove_item_node["direction"], "outgoing")
        self.assertEqual(remove_item_node["node_type"], "method")
        self.assertEqual(remove_item_node["symbol_name"], "remove_item")
        self.assertEqual(remove_item_node["qualified_name"], "shop/cart.py::ShoppingCart::remove_item")
        self.assertEqual(remove_item_node["file_path"], "shop/cart.py")
        self.assertGreater(remove_item_node["line"], 0)

    def test_results_are_deterministic(self):
        # Python's underlying dict/set iteration can be non-deterministic,
        # but get_code_neighbors sorts by relationship + direction + neighbor_id
        res1 = get_code_neighbors(self.graph, "shop/cart.py::ShoppingCart", direction="both")
        res2 = get_code_neighbors(self.graph, "shop/cart.py::ShoppingCart", direction="both")

        # Check order is exactly identical
        ids1 = [n["neighbor_id"] for n in res1]
        ids2 = [n["neighbor_id"] for n in res2]
        self.assertEqual(ids1, ids2)

        # Ensure it's actually sorted
        sorted_res = sorted(res1, key=lambda x: (x["relationship"], x["direction"], x["neighbor_id"]))
        ids_sorted = [n["neighbor_id"] for n in sorted_res]
        self.assertEqual(ids1, ids_sorted)

if __name__ == "__main__":
    unittest.main()
