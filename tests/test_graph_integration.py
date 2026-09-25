"""Integration tests for Stage 3 Task 4 — Graph-aware ToolRegistry and Agent.

Tests cover:
  1. Graph disabled: existing tools continue working
  2. Graph enabled: CodeGraph is constructed and available
  3. get_code_neighbors() invocable through ToolRegistry
  4. get_code_subgraph() invocable through ToolRegistry
  5. Tool arguments are passed correctly
  6. Invalid graph tool arguments are handled cleanly
  7. Existing Stage 1 tests remain unaffected
  8. Graph disabled returns informative message
  9. Unknown node returns informative message
  10. End-to-end: semantic concept -> graph query -> structured result
"""

import unittest
from pathlib import Path

SANDBOX = str(Path(__file__).parent.parent / "sandbox" / "mini_shop")


# ---------------------------------------------------------------------------
# 1. ToolRegistry without graph (backward compatibility)
# ---------------------------------------------------------------------------
class TestToolRegistryGraphDisabled(unittest.TestCase):

    def setUp(self):
        from mini_swe_agent.tools import ToolRegistry
        self.tools = ToolRegistry(SANDBOX)  # code_graph=None by default

    def test_code_graph_is_none(self):
        self.assertIsNone(self.tools.code_graph)

    def test_existing_list_files_works(self):
        result = self.tools.list_files()
        self.assertIn("pricing.py", result)

    def test_existing_read_file_works(self):
        result = self.tools.read_file("shop/pricing.py")
        self.assertIn("calculate_discount", result)

    def test_existing_search_code_works(self):
        result = self.tools.search_code("discount")
        self.assertIn("pricing.py", result)

    def test_get_code_neighbors_disabled_returns_message(self):
        result = self.tools.get_code_neighbors("shop/cart.py::ShoppingCart")
        self.assertIn("not configured", result)

    def test_get_code_subgraph_disabled_returns_message(self):
        result = self.tools.get_code_subgraph("shop/cart.py::ShoppingCart")
        self.assertIn("not configured", result)

    def test_execute_unknown_tool(self):
        result = self.tools.execute("nonexistent_tool", {})
        self.assertIn("Unknown tool", result)

    def test_graph_tools_listed_in_execute_even_when_disabled(self):
        # The tools are listed in the map even if graph is None
        result = self.tools.execute("get_code_neighbors", {"node_id": "shop/cart.py"})
        self.assertIn("not configured", result)


# ---------------------------------------------------------------------------
# 2. ToolRegistry with graph enabled
# ---------------------------------------------------------------------------
class TestToolRegistryGraphEnabled(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from mini_swe_agent.tools import ToolRegistry
        from mini_swe_agent.graph import CodeGraphBuilder
        builder = CodeGraphBuilder(SANDBOX)
        cls.code_graph = builder.build()
        cls.tools = ToolRegistry(SANDBOX, code_graph=cls.code_graph)

    def test_code_graph_is_set(self):
        self.assertIsNotNone(self.tools.code_graph)

    def test_get_code_neighbors_via_method(self):
        result = self.tools.get_code_neighbors(
            "shop/cart.py::ShoppingCart", direction="outgoing"
        )
        self.assertIn("Neighbors of", result)
        self.assertIn("remove_item", result)

    def test_get_code_neighbors_via_execute(self):
        result = self.tools.execute("get_code_neighbors", {
            "node_id": "shop/cart.py::ShoppingCart",
            "direction": "outgoing",
        })
        self.assertIn("Neighbors of", result)
        self.assertIn("remove_item", result)

    def test_get_code_subgraph_via_method(self):
        result = self.tools.get_code_subgraph(
            "shop/cart.py::ShoppingCart", max_depth=1, direction="outgoing"
        )
        self.assertIn("Subgraph rooted at", result)
        self.assertIn("remove_item", result)

    def test_get_code_subgraph_via_execute(self):
        result = self.tools.execute("get_code_subgraph", {
            "node_id": "shop/cart.py::ShoppingCart",
            "max_depth": 1,
            "direction": "outgoing",
        })
        self.assertIn("Subgraph rooted at", result)

    def test_arguments_passed_correctly_direction(self):
        outgoing = self.tools.get_code_neighbors(
            "shop/cart.py::ShoppingCart::total_with_discount", direction="outgoing"
        )
        incoming = self.tools.get_code_neighbors(
            "shop/cart.py::ShoppingCart::total_with_discount", direction="incoming"
        )
        # outgoing = calls; incoming = contains (from class)
        self.assertIn("outgoing", outgoing)
        self.assertIn("incoming", incoming)

    def test_arguments_passed_correctly_max_depth(self):
        depth1 = self.tools.get_code_subgraph(
            "shop/cart.py::ShoppingCart", max_depth=1, direction="outgoing"
        )
        depth0 = self.tools.get_code_subgraph(
            "shop/cart.py::ShoppingCart", max_depth=0, direction="outgoing"
        )
        self.assertIn("Discovered 0 node(s)", depth0)
        self.assertNotIn("Discovered 0 node(s)", depth1)

    def test_invalid_direction_returns_error(self):
        result = self.tools.get_code_neighbors(
            "shop/cart.py::ShoppingCart", direction="sideways"
        )
        self.assertIn("Error", result)

    def test_invalid_max_depth_returns_error(self):
        result = self.tools.get_code_subgraph(
            "shop/cart.py::ShoppingCart", max_depth=-1
        )
        self.assertIn("Error", result)

    def test_unknown_node_returns_informative_message(self):
        result = self.tools.get_code_neighbors("does_not_exist::nope")
        self.assertIn("not found", result)

    def test_unknown_node_subgraph_returns_informative_message(self):
        result = self.tools.get_code_subgraph("does_not_exist::nope")
        self.assertIn("not found", result)


# ---------------------------------------------------------------------------
# 3. MiniSWEAgent with enable_graph=False (default, backward compatible)
# ---------------------------------------------------------------------------
class TestAgentGraphDisabled(unittest.TestCase):

    def setUp(self):
        from mini_swe_agent.agent import MiniSWEAgent
        self.agent = MiniSWEAgent(SANDBOX, verbose=False, enable_graph=False)

    def test_enable_graph_false_by_default(self):
        self.assertFalse(self.agent.enable_graph)

    def test_code_graph_is_none(self):
        self.assertIsNone(self.agent.tools.code_graph)

    def test_standard_tools_still_accessible(self):
        result = self.agent.tools.list_files()
        self.assertIn("pricing.py", result)


# ---------------------------------------------------------------------------
# 4. MiniSWEAgent with enable_graph=True
# ---------------------------------------------------------------------------
class TestAgentGraphEnabled(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from mini_swe_agent.agent import MiniSWEAgent
        cls.agent = MiniSWEAgent(SANDBOX, verbose=False, enable_graph=True)

    def test_enable_graph_true(self):
        self.assertTrue(self.agent.enable_graph)

    def test_code_graph_is_not_none(self):
        self.assertIsNotNone(self.agent.tools.code_graph)

    def test_graph_tool_accessible_through_agent(self):
        result = self.agent.tools.get_code_neighbors(
            "shop/cart.py::ShoppingCart::remove_item", direction="outgoing"
        )
        self.assertIn("Neighbors of", result)
        self.assertIn("ItemNotFoundError", result)

    def test_graph_and_standard_tools_coexist(self):
        list_result = self.agent.tools.list_files()
        self.assertIn("pricing.py", list_result)
        graph_result = self.agent.tools.get_code_neighbors("shop/cart.py")
        self.assertIn("Neighbors of", graph_result)


# ---------------------------------------------------------------------------
# 5. End-to-end integration: relevant code -> graph query -> structured result
# ---------------------------------------------------------------------------
class TestEndToEndGraphIntegration(unittest.TestCase):
    """
    Demonstrates the pipeline:
      Issue -> relevant node (known from issue/search) -> graph query -> structured context
    """

    @classmethod
    def setUpClass(cls):
        from mini_swe_agent.tools import ToolRegistry
        from mini_swe_agent.graph import CodeGraphBuilder
        builder = CodeGraphBuilder(SANDBOX)
        cls.code_graph = builder.build()
        cls.tools = ToolRegistry(SANDBOX, code_graph=cls.code_graph)

    def test_pipeline_neighbors(self):
        """
        Issue: "discount percentage calculation is incorrect"
        Known relevant node: shop/pricing.py::calculate_discount
        Query: what calls this function?
        """
        # Step 1: we know (or found via search_similar_code) the relevant node
        relevant_node = "shop/pricing.py::calculate_discount"

        # Step 2: get neighbors to understand context
        result = self.tools.get_code_neighbors(relevant_node, direction="incoming")

        # The function is called by total_with_discount, which should appear as a caller
        self.assertIn("Neighbors of", result)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_pipeline_subgraph(self):
        """
        Issue: "remove_item raises unhandled KeyError"
        Known relevant node: shop/cart.py::ShoppingCart::remove_item
        Query: what is the surrounding structure (depth 2)?
        """
        relevant_node = "shop/cart.py::ShoppingCart::remove_item"

        result = self.tools.get_code_subgraph(relevant_node, max_depth=2, direction="both")

        self.assertIn("Subgraph rooted at", result)
        self.assertIn("remove_item", result)
        # Depth 2 should reach the module level and call targets
        self.assertIn("depth", result)

    def test_result_is_llm_consumable_string(self):
        """The tool result is a plain string suitable for LLM context injection."""
        result = self.tools.get_code_subgraph(
            "shop/cart.py::ShoppingCart", max_depth=1, direction="outgoing"
        )
        self.assertIsInstance(result, str)
        # Should be multi-line structured output
        self.assertIn("\n", result)


if __name__ == "__main__":
    unittest.main()
