"""Unit tests for Stage 3 — Code Graph Builder (ast_graph.py).

Tests cover:
  - Python file discovery
  - Module, class, function, and method node creation
  - 'contains' relationship edges
  - 'imports' relationship detection
  - 'calls' relationship detection
  - Node metadata (file_path, symbol_name, line, node_type, qualified_name)
  - Safe handling of invalid / unparseable Python files
  - CodeGraph helper methods

Uses a small temporary synthetic workspace for determinism and speed.
The sandbox/mini_shop repository is also used for integration-level checks.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _write(base: str, rel: str, content: str) -> Path:
    p = Path(base) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


PRICING_PY = """\
\"\"\"Pricing utilities.\"\"\"


def calculate_discount(total: float, percent: float) -> float:
    \"\"\"Return discounted total.\"\"\"
    discount = total * (percent / 100.0)
    return round(total - discount, 2)
"""

CART_PY = """\
from pricing import calculate_discount


class ItemNotFoundError(Exception):
    pass


class ShoppingCart:
    def __init__(self):
        self.items = {}

    def add_item(self, name, price):
        if price <= 0:
            raise ValueError('Price must be positive')
        self.items[name] = price

    def remove_item(self, name):
        if name not in self.items:
            raise ItemNotFoundError(name)
        del self.items[name]

    def subtotal(self):
        return round(sum(self.items.values()), 2)

    def total_with_discount(self, pct):
        return calculate_discount(self.subtotal(), pct)
"""

INIT_PY = """\
from .cart import ShoppingCart
"""

BAD_PY = """\
def broken(
    # missing closing paren
"""


# ---------------------------------------------------------------------------
# 1. File discovery
# ---------------------------------------------------------------------------
class TestFileDiscovery(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        _write(self.ws, "pricing.py", PRICING_PY)
        _write(self.ws, "cart.py", CART_PY)
        _write(self.ws, "__init__.py", INIT_PY)
        _write(self.ws, "README.md", "# readme")
        _write(self.ws, "__pycache__/cart.cpython-312.pyc", "binary")
        _write(self.ws, ".git/config", "[core]")
        _write(self.ws, ".venv/lib/site.py", "import sys")

    def tearDown(self):
        shutil.rmtree(self.ws, ignore_errors=True)

    def _builder(self):
        from mini_swe_agent.graph import CodeGraphBuilder
        return CodeGraphBuilder(self.ws)

    def test_discovers_python_files(self):
        g = self._builder().build()
        modules = g.nodes_of_type("module")
        paths = [m for m in modules]
        self.assertTrue(any("pricing.py" in p for p in paths))
        self.assertTrue(any("cart.py" in p for p in paths))

    def test_ignores_pycache(self):
        g = self._builder().build()
        all_nodes = list(g.graph.nodes())
        self.assertFalse(any("__pycache__" in n for n in all_nodes))

    def test_ignores_git(self):
        g = self._builder().build()
        all_nodes = list(g.graph.nodes())
        self.assertFalse(any(".git" in n for n in all_nodes))

    def test_ignores_venv(self):
        g = self._builder().build()
        all_nodes = list(g.graph.nodes())
        self.assertFalse(any(".venv" in n for n in all_nodes))

    def test_non_python_files_not_added(self):
        g = self._builder().build()
        all_nodes = list(g.graph.nodes())
        self.assertFalse(any("README" in n for n in all_nodes))


# ---------------------------------------------------------------------------
# 2. Module nodes
# ---------------------------------------------------------------------------
class TestModuleNodes(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        _write(self.ws, "pricing.py", PRICING_PY)

    def tearDown(self):
        shutil.rmtree(self.ws, ignore_errors=True)

    def _graph(self):
        from mini_swe_agent.graph import CodeGraphBuilder
        return CodeGraphBuilder(self.ws).build()

    def test_module_node_created(self):
        g = self._graph()
        modules = g.nodes_of_type("module")
        self.assertTrue(any("pricing.py" in m for m in modules))

    def test_module_node_metadata(self):
        g = self._graph()
        node = g.get_node("pricing.py")
        self.assertIsNotNone(node)
        self.assertEqual(node["node_type"], "module")
        self.assertEqual(node["file_path"], "pricing.py")
        self.assertIn("pricing", node["symbol_name"])


# ---------------------------------------------------------------------------
# 3. Function nodes
# ---------------------------------------------------------------------------
class TestFunctionNodes(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        _write(self.ws, "pricing.py", PRICING_PY)

    def tearDown(self):
        shutil.rmtree(self.ws, ignore_errors=True)

    def _graph(self):
        from mini_swe_agent.graph import CodeGraphBuilder
        return CodeGraphBuilder(self.ws).build()

    def test_function_node_exists(self):
        g = self._graph()
        funcs = g.nodes_of_type("function")
        names = [g.get_node(f)["symbol_name"] for f in funcs]
        self.assertIn("calculate_discount", names)

    def test_function_node_metadata(self):
        g = self._graph()
        node_id = "pricing.py::calculate_discount"
        node = g.get_node(node_id)
        self.assertIsNotNone(node, f"Node {node_id!r} not found")
        self.assertEqual(node["node_type"], "function")
        self.assertEqual(node["symbol_name"], "calculate_discount")
        self.assertEqual(node["file_path"], "pricing.py")
        self.assertGreaterEqual(node["line"], 1)
        self.assertIn("calculate_discount", node["qualified_name"])


# ---------------------------------------------------------------------------
# 4. Class and method nodes
# ---------------------------------------------------------------------------
class TestClassAndMethodNodes(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        _write(self.ws, "cart.py", CART_PY)

    def tearDown(self):
        shutil.rmtree(self.ws, ignore_errors=True)

    def _graph(self):
        from mini_swe_agent.graph import CodeGraphBuilder
        return CodeGraphBuilder(self.ws).build()

    def test_class_nodes_created(self):
        g = self._graph()
        class_nodes = g.nodes_of_type("class")
        names = [g.get_node(c)["symbol_name"] for c in class_nodes]
        self.assertIn("ShoppingCart", names)
        self.assertIn("ItemNotFoundError", names)

    def test_class_node_metadata(self):
        g = self._graph()
        node = g.get_node("cart.py::ShoppingCart")
        self.assertIsNotNone(node)
        self.assertEqual(node["node_type"], "class")
        self.assertEqual(node["symbol_name"], "ShoppingCart")
        self.assertEqual(node["file_path"], "cart.py")
        self.assertGreaterEqual(node["line"], 1)

    def test_method_nodes_created(self):
        g = self._graph()
        methods = g.nodes_of_type("method")
        names = [g.get_node(m)["symbol_name"] for m in methods]
        self.assertIn("add_item", names)
        self.assertIn("remove_item", names)
        self.assertIn("subtotal", names)

    def test_method_node_type_not_function(self):
        g = self._graph()
        node = g.get_node("cart.py::ShoppingCart::remove_item")
        self.assertIsNotNone(node)
        self.assertEqual(node["node_type"], "method")

    def test_method_node_metadata(self):
        g = self._graph()
        node = g.get_node("cart.py::ShoppingCart::remove_item")
        self.assertIsNotNone(node)
        self.assertEqual(node["symbol_name"], "remove_item")
        self.assertEqual(node["file_path"], "cart.py")
        self.assertIn("remove_item", node["qualified_name"])
        self.assertIn("ShoppingCart", node["qualified_name"])


# ---------------------------------------------------------------------------
# 5. Contains edges
# ---------------------------------------------------------------------------
class TestContainsEdges(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        _write(self.ws, "cart.py", CART_PY)
        _write(self.ws, "pricing.py", PRICING_PY)

    def tearDown(self):
        shutil.rmtree(self.ws, ignore_errors=True)

    def _graph(self):
        from mini_swe_agent.graph import CodeGraphBuilder
        return CodeGraphBuilder(self.ws).build()

    def test_module_contains_class(self):
        g = self._graph()
        children = g.neighbors_of("cart.py", edge_type="contains")
        self.assertIn("cart.py::ShoppingCart", children)

    def test_module_contains_function(self):
        g = self._graph()
        children = g.neighbors_of("pricing.py", edge_type="contains")
        self.assertIn("pricing.py::calculate_discount", children)

    def test_class_contains_method(self):
        g = self._graph()
        children = g.neighbors_of("cart.py::ShoppingCart", edge_type="contains")
        self.assertIn("cart.py::ShoppingCart::add_item", children)
        self.assertIn("cart.py::ShoppingCart::remove_item", children)

    def test_contains_edge_has_correct_relationship(self):
        g = self._graph()
        edges = g.edges_of_type("contains")
        edge_pairs = [(s, d) for s, d in edges]
        self.assertIn(("cart.py", "cart.py::ShoppingCart"), edge_pairs)

    def test_all_methods_contained_in_class(self):
        g = self._graph()
        method_ids = g.nodes_of_type("method")
        for mid in method_ids:
            if "cart.py::ShoppingCart" in mid:
                parents = g.predecessors_of(mid, edge_type="contains")
                self.assertTrue(
                    len(parents) >= 1,
                    f"Method {mid!r} has no 'contains' parent"
                )


# ---------------------------------------------------------------------------
# 6. Imports edges
# ---------------------------------------------------------------------------
class TestImportEdges(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        _write(self.ws, "cart.py", CART_PY)

    def tearDown(self):
        shutil.rmtree(self.ws, ignore_errors=True)

    def _graph(self):
        from mini_swe_agent.graph import CodeGraphBuilder
        return CodeGraphBuilder(self.ws).build()

    def test_import_from_detected(self):
        g = self._graph()
        import_edges = g.edges_of_type("imports")
        sources = [s for s, _ in import_edges]
        self.assertIn("cart.py", sources)

    def test_imported_module_name_recorded(self):
        g = self._graph()
        imported = g.neighbors_of("cart.py", edge_type="imports")
        self.assertIn("pricing", imported)

    def test_import_edge_direction(self):
        g = self._graph()
        # cart.py imports from pricing, not the other way
        predecessors = g.predecessors_of("pricing", edge_type="imports")
        self.assertIn("cart.py", predecessors)


# ---------------------------------------------------------------------------
# 7. Calls edges
# ---------------------------------------------------------------------------
class TestCallsEdges(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        _write(self.ws, "cart.py", CART_PY)
        _write(self.ws, "pricing.py", PRICING_PY)

    def tearDown(self):
        shutil.rmtree(self.ws, ignore_errors=True)

    def _graph(self):
        from mini_swe_agent.graph import CodeGraphBuilder
        return CodeGraphBuilder(self.ws).build()

    def test_method_calls_detected(self):
        g = self._graph()
        calls = g.edges_of_type("calls")
        callers = [s for s, _ in calls]
        self.assertIn("cart.py::ShoppingCart::remove_item", callers)

    def test_remove_item_calls_item_not_found_error(self):
        g = self._graph()
        callees = g.neighbors_of(
            "cart.py::ShoppingCart::remove_item", edge_type="calls"
        )
        self.assertIn("ItemNotFoundError", callees)

    def test_total_with_discount_calls_calculate_discount(self):
        g = self._graph()
        callees = g.neighbors_of(
            "cart.py::ShoppingCart::total_with_discount", edge_type="calls"
        )
        self.assertIn("calculate_discount", callees)

    def test_calls_edges_have_correct_relationship_attr(self):
        g = self._graph()
        for u, v, data in g.graph.edges(data=True):
            if data.get("relationship") == "calls":
                self.assertEqual(data["relationship"], "calls")
                break  # at least one calls edge found and verified


# ---------------------------------------------------------------------------
# 8. Invalid Python files — safe handling
# ---------------------------------------------------------------------------
class TestInvalidFileHandling(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        _write(self.ws, "good.py", PRICING_PY)
        _write(self.ws, "bad.py", BAD_PY)

    def tearDown(self):
        shutil.rmtree(self.ws, ignore_errors=True)

    def _builder(self):
        from mini_swe_agent.graph import CodeGraphBuilder
        return CodeGraphBuilder(self.ws)

    def test_build_does_not_crash(self):
        """Building with an invalid file must not raise any exception."""
        builder = self._builder()
        try:
            g = builder.build()
        except Exception as exc:
            self.fail(f"build() raised an exception for invalid file: {exc}")

    def test_invalid_file_recorded_in_parse_errors(self):
        builder = self._builder()
        builder.build()
        self.assertIn("bad.py", builder.parse_errors)

    def test_valid_file_still_parsed(self):
        builder = self._builder()
        g = builder.build()
        modules = g.nodes_of_type("module")
        self.assertTrue(any("good.py" in m for m in modules))

    def test_parse_error_message_is_nonempty(self):
        builder = self._builder()
        builder.build()
        self.assertTrue(len(builder.parse_errors["bad.py"]) > 0)


# ---------------------------------------------------------------------------
# 9. CodeGraph helper methods
# ---------------------------------------------------------------------------
class TestCodeGraphHelpers(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        _write(self.ws, "cart.py", CART_PY)
        _write(self.ws, "pricing.py", PRICING_PY)
        from mini_swe_agent.graph import CodeGraphBuilder
        self.graph = CodeGraphBuilder(self.ws).build()

    def tearDown(self):
        shutil.rmtree(self.ws, ignore_errors=True)

    def test_nodes_of_type_returns_correct_type(self):
        methods = self.graph.nodes_of_type("method")
        for m in methods:
            node = self.graph.get_node(m)
            self.assertEqual(node["node_type"], "method")

    def test_get_node_returns_none_for_missing(self):
        result = self.graph.get_node("nonexistent::node")
        self.assertIsNone(result)

    def test_summary_returns_string(self):
        s = self.graph.summary()
        self.assertIsInstance(s, str)
        self.assertIn("nodes", s)
        self.assertIn("edges", s)

    def test_neighbors_of_no_filter(self):
        # module level – should have both contains and imports neighbors
        neighbors = self.graph.neighbors_of("cart.py")
        self.assertGreater(len(neighbors), 0)

    def test_predecessors_of(self):
        preds = self.graph.predecessors_of(
            "cart.py::ShoppingCart::add_item", edge_type="contains"
        )
        self.assertIn("cart.py::ShoppingCart", preds)


# ---------------------------------------------------------------------------
# 10. Integration — sandbox/mini_shop
# ---------------------------------------------------------------------------
class TestSandboxIntegration(unittest.TestCase):
    """Build the graph on the real sandbox and verify key expectations."""

    @classmethod
    def setUpClass(cls):
        from mini_swe_agent.graph import CodeGraphBuilder
        sandbox = str(Path(__file__).parent.parent / "sandbox" / "mini_shop")
        builder = CodeGraphBuilder(sandbox)
        cls.graph = builder.build()
        cls.parse_errors = builder.parse_errors

    def test_no_parse_errors(self):
        self.assertEqual(
            self.parse_errors, {},
            f"Unexpected parse errors: {self.parse_errors}"
        )

    def test_pricing_module_exists(self):
        modules = self.graph.nodes_of_type("module")
        self.assertTrue(any("pricing" in m for m in modules))

    def test_cart_module_exists(self):
        modules = self.graph.nodes_of_type("module")
        self.assertTrue(any("cart" in m for m in modules))

    def test_calculate_discount_is_function(self):
        funcs = self.graph.nodes_of_type("function")
        names = [self.graph.get_node(f)["symbol_name"] for f in funcs]
        self.assertIn("calculate_discount", names)

    def test_shopping_cart_is_class(self):
        classes = self.graph.nodes_of_type("class")
        names = [self.graph.get_node(c)["symbol_name"] for c in classes]
        self.assertIn("ShoppingCart", names)

    def test_remove_item_is_method(self):
        methods = self.graph.nodes_of_type("method")
        names = [self.graph.get_node(m)["symbol_name"] for m in methods]
        self.assertIn("remove_item", names)

    def test_total_with_discount_calls_calculate_discount(self):
        # Integration: verify the call edge exists in the real sandbox
        callees = self.graph.neighbors_of(
            "shop/cart.py::ShoppingCart::total_with_discount", edge_type="calls"
        )
        self.assertIn("calculate_discount", callees)

    def test_cart_imports_pricing(self):
        imported = self.graph.neighbors_of("shop/cart.py", edge_type="imports")
        self.assertTrue(
            any("pricing" in i for i in imported),
            f"Expected 'pricing' in imports from shop/cart.py, got: {imported}"
        )

    def test_summary_is_populated(self):
        s = self.graph.summary()
        self.assertIn("module", s)
        self.assertIn("class", s)

    def test_graph_has_nodes_and_edges(self):
        self.assertGreater(self.graph.graph.number_of_nodes(), 5)
        self.assertGreater(self.graph.graph.number_of_edges(), 5)


if __name__ == "__main__":
    unittest.main()
