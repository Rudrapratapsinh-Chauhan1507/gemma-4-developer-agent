"""Unit tests for Stage 3 — Code Graph Subgraph (graph_query.py).

Tests cover:
  - max_depth=0 returns only the root
  - max_depth=1 returns immediate neighbors
  - max_depth=2 discovers a second-hop node
  - outgoing traversal
  - incoming traversal
  - both-direction traversal
  - isolated node
  - unknown node
  - invalid direction
  - negative max_depth
  - non-integer max_depth
  - cycles do not cause infinite traversal
  - duplicate paths do not duplicate nodes
  - minimum depth is retained when multiple paths reach a node
  - returned node metadata is correct
  - returned edge metadata is correct
  - deterministic result ordering
  - integration test using sandbox/mini_shop
"""

import unittest
from pathlib import Path
import networkx as nx

from mini_swe_agent.graph.ast_graph import CodeGraph
from mini_swe_agent.graph.graph_query import get_code_subgraph
from mini_swe_agent.graph import CodeGraphBuilder

class TestGraphSubgraph(unittest.TestCase):

    def setUp(self):
        # Create a synthetic graph for controlled cycle testing
        G = nx.DiGraph()
        # A -> B -> C -> A (cycle)
        # A -> D -> C (multiple paths to C, depth 2)
        # E -> A (incoming to A)

        G.add_node("A", node_type="function", symbol_name="A", file_path="test.py", line=1)
        G.add_node("B", node_type="function", symbol_name="B", file_path="test.py", line=2)
        G.add_node("C", node_type="function", symbol_name="C", file_path="test.py", line=3)
        G.add_node("D", node_type="function", symbol_name="D", file_path="test.py", line=4)
        G.add_node("E", node_type="function", symbol_name="E", file_path="test.py", line=5)
        G.add_node("Isolated", node_type="function")

        G.add_edge("A", "B", relationship="calls")
        G.add_edge("B", "C", relationship="calls")
        G.add_edge("C", "A", relationship="calls") # cycle

        G.add_edge("A", "D", relationship="calls")
        G.add_edge("D", "C", relationship="calls") # C reachable via A->B->C and A->D->C

        G.add_edge("E", "A", relationship="calls")

        self.synth_graph = CodeGraph(G)

    def test_max_depth_0(self):
        res = get_code_subgraph(self.synth_graph, "A", max_depth=0)
        self.assertEqual(res["root"]["node_id"], "A")
        self.assertEqual(res["nodes"], [])
        self.assertEqual(res["edges"], [])

    def test_max_depth_1(self):
        res = get_code_subgraph(self.synth_graph, "A", max_depth=1, direction="outgoing")
        node_ids = [n["node_id"] for n in res["nodes"]]
        self.assertCountEqual(node_ids, ["B", "D"])
        self.assertEqual(len(res["edges"]), 2)

        for n in res["nodes"]:
            self.assertEqual(n["depth"], 1)

    def test_max_depth_2_discovers_second_hop(self):
        res = get_code_subgraph(self.synth_graph, "A", max_depth=2, direction="outgoing")
        node_ids = [n["node_id"] for n in res["nodes"]]
        self.assertCountEqual(node_ids, ["B", "D", "C"])

        # C is reachable at depth 2
        c_node = next(n for n in res["nodes"] if n["node_id"] == "C")
        self.assertEqual(c_node["depth"], 2)

    def test_outgoing_traversal(self):
        res = get_code_subgraph(self.synth_graph, "B", max_depth=1, direction="outgoing")
        node_ids = [n["node_id"] for n in res["nodes"]]
        self.assertEqual(node_ids, ["C"])

    def test_incoming_traversal(self):
        res = get_code_subgraph(self.synth_graph, "A", max_depth=1, direction="incoming")
        node_ids = [n["node_id"] for n in res["nodes"]]
        self.assertCountEqual(node_ids, ["E", "C"]) # C calls A, E calls A

    def test_both_direction_traversal(self):
        res = get_code_subgraph(self.synth_graph, "A", max_depth=1, direction="both")
        node_ids = [n["node_id"] for n in res["nodes"]]
        # outgoing: B, D. incoming: C, E
        self.assertCountEqual(node_ids, ["B", "D", "C", "E"])

    def test_isolated_node(self):
        res = get_code_subgraph(self.synth_graph, "Isolated", max_depth=2)
        self.assertEqual(res["root"]["node_id"], "Isolated")
        self.assertEqual(res["nodes"], [])
        self.assertEqual(res["edges"], [])

    def test_unknown_node(self):
        res = get_code_subgraph(self.synth_graph, "Unknown", max_depth=2)
        self.assertIsNone(res["root"])
        self.assertEqual(res["nodes"], [])
        self.assertEqual(res["edges"], [])

    def test_invalid_direction(self):
        with self.assertRaises(ValueError):
            get_code_subgraph(self.synth_graph, "A", direction="invalid")

    def test_negative_max_depth(self):
        with self.assertRaises(ValueError):
            get_code_subgraph(self.synth_graph, "A", max_depth=-1)

    def test_non_integer_max_depth(self):
        with self.assertRaises(TypeError):
            get_code_subgraph(self.synth_graph, "A", max_depth=1.5)
        with self.assertRaises(TypeError):
            get_code_subgraph(self.synth_graph, "A", max_depth="1")

    def test_cycles_do_not_cause_infinite_traversal(self):
        # A -> B -> C -> A
        res = get_code_subgraph(self.synth_graph, "A", max_depth=10, direction="outgoing")
        node_ids = [n["node_id"] for n in res["nodes"]]
        self.assertCountEqual(node_ids, ["B", "C", "D"])

        # Check depth mapping: A(0), B(1), D(1), C(2)
        c_node = next(n for n in res["nodes"] if n["node_id"] == "C")
        self.assertEqual(c_node["depth"], 2)

    def test_duplicate_paths_do_not_duplicate_nodes(self):
        res = get_code_subgraph(self.synth_graph, "A", max_depth=3, direction="outgoing")
        c_nodes = [n for n in res["nodes"] if n["node_id"] == "C"]
        self.assertEqual(len(c_nodes), 1)

    def test_minimum_depth_retained(self):
        # Add an edge directly from A to C
        self.synth_graph.graph.add_edge("A", "C", relationship="calls")
        # Now C is reachable via A->C (depth 1) and A->B->C (depth 2)
        res = get_code_subgraph(self.synth_graph, "A", max_depth=3, direction="outgoing")
        c_node = next(n for n in res["nodes"] if n["node_id"] == "C")
        self.assertEqual(c_node["depth"], 1)

    def test_metadata_correctness(self):
        res = get_code_subgraph(self.synth_graph, "A", max_depth=1, direction="outgoing")
        b_node = next(n for n in res["nodes"] if n["node_id"] == "B")
        self.assertEqual(b_node["node_type"], "function")
        self.assertEqual(b_node["symbol_name"], "B")

        edge = next(e for e in res["edges"] if e["source"] == "A" and e["target"] == "B")
        self.assertEqual(edge["relationship"], "calls")
        self.assertEqual(edge["direction"], "outgoing")

    def test_deterministic_ordering(self):
        res = get_code_subgraph(self.synth_graph, "A", max_depth=2, direction="both")

        # Nodes should be sorted by depth, then node_id
        depths = [n["depth"] for n in res["nodes"]]
        self.assertEqual(depths, sorted(depths))

        # Check stable order explicitly
        node_ids = [n["node_id"] for n in res["nodes"]]
        # Since C calls A, direction="both" reaches C from A via incoming edge, so C is depth 1.
        expected = ["B", "C", "D", "E"]
        self.assertEqual(node_ids, expected)

        # Edges should be sorted by source, target, relationship
        edges = [(e["source"], e["target"]) for e in res["edges"]]
        self.assertEqual(edges, sorted(edges))


class TestGraphSubgraphIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Build the graph on the real sandbox for integration tests."""
        cls.sandbox = str(Path(__file__).parent.parent / "sandbox" / "mini_shop")
        builder = CodeGraphBuilder(cls.sandbox)
        cls.graph = builder.build()

    def test_sandbox_integration_max_depth_2(self):
        # We know total_with_discount calls calculate_discount
        node = "shop/cart.py::ShoppingCart::total_with_discount"
        res = get_code_subgraph(self.graph, node, max_depth=2, direction="outgoing")

        self.assertEqual(res["root"]["node_id"], node)
        self.assertTrue(len(res["nodes"]) > 0)
        self.assertTrue(len(res["edges"]) > 0)

        # Should contain calculate_discount at depth 1.
        # Note: Task 1 notes that call targets are just strings ("calculate_discount")
        # and not fully resolved to qualified names yet.
        calc_discount = "calculate_discount"
        calc_node = next((n for n in res["nodes"] if n["node_id"] == calc_discount), None)
        self.assertIsNotNone(calc_node)
        self.assertEqual(calc_node["depth"], 1)

if __name__ == "__main__":
    unittest.main()
