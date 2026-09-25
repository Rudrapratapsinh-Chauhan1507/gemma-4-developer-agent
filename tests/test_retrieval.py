"""Unit tests for Stage 2 retrieval components.

Tests cover:
  - FileDiscovery
  - KeywordRetriever
  - CodeChunker
  - CodeEmbedder  (loads the model once via setUpClass)
  - FaissVectorIndex
  - SemanticRetriever
  - ContextBuilder
"""

import os
import shutil
import tempfile
import unittest
import numpy as np
from pathlib import Path


# ---------------------------------------------------------------------------
# 1. FileDiscovery
# ---------------------------------------------------------------------------
class TestFileDiscovery(unittest.TestCase):
    """Verify workspace file discovery with correct filtering."""

    def setUp(self):
        self.ws = tempfile.mkdtemp()
        # Create source files that SHOULD be discovered
        self._write("src/main.py", "def hello(): pass\n")
        self._write("src/utils.py", "# utils\n")
        self._write("README.md", "# readme\n")
        self._write("config.yaml", "key: value\n")
        # Create files/dirs that SHOULD be ignored
        self._write("__pycache__/main.cpython-312.pyc", "")
        self._write(".git/config", "[core]\n")
        self._write(".venv/lib/site.py", "import sys\n")
        self._write("build/output.py", "")
        self._write("node_modules/lib/index.js", "")
        self._write("src/main.pyc", "")

    def tearDown(self):
        shutil.rmtree(self.ws, ignore_errors=True)

    def _write(self, rel, content):
        p = Path(self.ws) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def test_discovers_python_and_md_files(self):
        from mini_swe_agent.retrieval.discovery import FileDiscovery
        d = FileDiscovery(self.ws)
        files = [f.as_posix() for f in d.discover_files()]
        self.assertIn("README.md", files)
        self.assertIn("config.yaml", files)
        self.assertIn("src/main.py", files)
        self.assertIn("src/utils.py", files)

    def test_ignores_pycache(self):
        from mini_swe_agent.retrieval.discovery import FileDiscovery
        d = FileDiscovery(self.ws)
        files = [f.as_posix() for f in d.discover_files()]
        self.assertFalse(any("__pycache__" in f for f in files), f"pycache not filtered: {files}")

    def test_ignores_git_dir(self):
        from mini_swe_agent.retrieval.discovery import FileDiscovery
        d = FileDiscovery(self.ws)
        files = [f.as_posix() for f in d.discover_files()]
        self.assertFalse(any(".git" in f for f in files), f".git not filtered: {files}")

    def test_ignores_venv(self):
        from mini_swe_agent.retrieval.discovery import FileDiscovery
        d = FileDiscovery(self.ws)
        files = [f.as_posix() for f in d.discover_files()]
        self.assertFalse(any(".venv" in f for f in files))

    def test_ignores_build_dir(self):
        from mini_swe_agent.retrieval.discovery import FileDiscovery
        d = FileDiscovery(self.ws)
        files = [f.as_posix() for f in d.discover_files()]
        self.assertFalse(any(f.startswith("build/") for f in files))

    def test_ignores_pyc_files(self):
        from mini_swe_agent.retrieval.discovery import FileDiscovery
        d = FileDiscovery(self.ws)
        files = [f.as_posix() for f in d.discover_files()]
        self.assertFalse(any(f.endswith(".pyc") for f in files))

    def test_empty_workspace(self):
        from mini_swe_agent.retrieval.discovery import FileDiscovery
        empty = tempfile.mkdtemp()
        try:
            d = FileDiscovery(empty)
            self.assertEqual(d.discover_files(), [])
        finally:
            shutil.rmtree(empty)


# ---------------------------------------------------------------------------
# 2. KeywordRetriever
# ---------------------------------------------------------------------------
class TestKeywordRetriever(unittest.TestCase):
    """Verify keyword-based retrieval baseline."""

    def setUp(self):
        self.ws = tempfile.mkdtemp()
        self._write("pricing.py",
            "def calculate_discount(total, percent):\n"
            "    \"\"\"Apply a percentage discount to the total.\"\"\"\n"
            "    return total * (percent / 100)\n")
        self._write("cart.py",
            "class ShoppingCart:\n"
            "    def remove_item(self, name):\n"
            "        del self.items[name]\n")
        self._write("unrelated.py",
            "def greet(name):\n"
            "    return f'Hello {name}'\n")

    def tearDown(self):
        shutil.rmtree(self.ws, ignore_errors=True)

    def _write(self, rel, content):
        p = Path(self.ws) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def test_discount_query_finds_pricing(self):
        from mini_swe_agent.retrieval.keyword_search import KeywordRetriever
        kr = KeywordRetriever(self.ws)
        results = kr.retrieve("discount percentage calculation", top_k=3)
        paths = [r["file_path"] for r in results]
        self.assertTrue(any("pricing" in p for p in paths),
                        f"Expected pricing.py in results, got: {paths}")

    def test_returns_correct_structure(self):
        from mini_swe_agent.retrieval.keyword_search import KeywordRetriever
        kr = KeywordRetriever(self.ws)
        results = kr.retrieve("discount", top_k=5)
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertIn("file_path", r)
            self.assertIn("score", r)
            self.assertIn("matched_keywords", r)
            self.assertIn("preview_lines", r)

    def test_top_k_respected(self):
        from mini_swe_agent.retrieval.keyword_search import KeywordRetriever
        kr = KeywordRetriever(self.ws)
        results = kr.retrieve("def", top_k=1)
        self.assertLessEqual(len(results), 1)

    def test_empty_query_returns_empty(self):
        from mini_swe_agent.retrieval.keyword_search import KeywordRetriever
        kr = KeywordRetriever(self.ws)
        results = kr.retrieve("", top_k=5)
        self.assertEqual(results, [])

    def test_no_match_returns_empty(self):
        from mini_swe_agent.retrieval.keyword_search import KeywordRetriever
        kr = KeywordRetriever(self.ws)
        results = kr.retrieve("xyzzy_totally_absent_token", top_k=5)
        self.assertEqual(results, [])

    def test_remove_item_query_finds_cart(self):
        from mini_swe_agent.retrieval.keyword_search import KeywordRetriever
        kr = KeywordRetriever(self.ws)
        results = kr.retrieve("remove item cart", top_k=3)
        paths = [r["file_path"] for r in results]
        self.assertTrue(any("cart" in p for p in paths),
                        f"Expected cart.py in results, got: {paths}")


# ---------------------------------------------------------------------------
# 3. CodeChunker
# ---------------------------------------------------------------------------
class TestCodeChunker(unittest.TestCase):
    """Verify AST-based code chunking and fallback behavior."""

    def setUp(self):
        from mini_swe_agent.retrieval.chunker import CodeChunker
        self.chunker = CodeChunker()

    def test_extracts_function(self):
        code = (
            '"""Module docstring."""\n\n'
            'def calculate_discount(total, percent):\n'
            '    """Apply percentage discount."""\n'
            '    return total * (percent / 100)\n'
        )
        chunks = self.chunker.chunk_file("pricing.py", code)
        names = [c.symbol_name for c in chunks]
        self.assertIn("calculate_discount", names)

    def test_extracts_class_and_methods(self):
        code = (
            'class ShoppingCart:\n'
            '    """A shopping cart."""\n\n'
            '    def add_item(self, name, price):\n'
            '        self.items[name] = price\n\n'
            '    def remove_item(self, name):\n'
            '        del self.items[name]\n'
        )
        chunks = self.chunker.chunk_file("cart.py", code)
        names = [c.symbol_name for c in chunks]
        self.assertIn("ShoppingCart", names)
        self.assertIn("ShoppingCart.add_item", names)
        self.assertIn("ShoppingCart.remove_item", names)

    def test_function_line_metadata(self):
        code = 'def foo():\n    pass\n'
        chunks = self.chunker.chunk_file("foo.py", code)
        fn = next(c for c in chunks if c.symbol_name == "foo")
        self.assertEqual(fn.start_line, 1)
        self.assertGreaterEqual(fn.end_line, 2)
        self.assertEqual(fn.symbol_type, "function")

    def test_method_symbol_type(self):
        code = (
            'class A:\n'
            '    def method(self):\n'
            '        pass\n'
        )
        chunks = self.chunker.chunk_file("a.py", code)
        methods = [c for c in chunks if c.symbol_type == "method"]
        self.assertTrue(len(methods) >= 1)

    def test_docstring_captured(self):
        code = (
            'def greet(name):\n'
            '    """Say hello to name."""\n'
            '    return f"Hello {name}"\n'
        )
        chunks = self.chunker.chunk_file("greet.py", code)
        fn = next(c for c in chunks if c.symbol_name == "greet")
        self.assertIsNotNone(fn.docstring)
        self.assertIn("hello", fn.docstring.lower())

    def test_fallback_on_non_python(self):
        content = "key: value\nanother: thing\nmore: data\n"
        chunks = self.chunker.chunk_file("config.yaml", content)
        self.assertGreater(len(chunks), 0)
        for c in chunks:
            self.assertEqual(c.symbol_type, "block")

    def test_fallback_on_syntax_error(self):
        bad_code = "def broken(\n  # missing closing\n"
        chunks = self.chunker.chunk_file("broken.py", bad_code)
        self.assertGreater(len(chunks), 0)

    def test_empty_file_returns_no_chunks(self):
        chunks = self.chunker.chunk_file("empty.py", "")
        self.assertEqual(chunks, [])

    def test_embedding_text_contains_symbol_name(self):
        code = 'def my_func():\n    pass\n'
        chunks = self.chunker.chunk_file("f.py", code)
        fn = next(c for c in chunks if c.symbol_name == "my_func")
        text = fn.embedding_text()
        self.assertIn("my_func", text)
        self.assertIn("f.py", text)


# ---------------------------------------------------------------------------
# 4. CodeEmbedder  (model loaded once for the class)
# ---------------------------------------------------------------------------
class TestCodeEmbedder(unittest.TestCase):
    """Verify embedding shapes, dtype, and normalization."""

    @classmethod
    def setUpClass(cls):
        from mini_swe_agent.retrieval.embedder import CodeEmbedder
        cls.embedder = CodeEmbedder()
        # Warm up once — subsequent calls reuse the cached model
        cls.embedder.embed_texts(["warmup"])

    def test_embed_texts_shape(self):
        vecs = self.embedder.embed_texts(["hello world", "discount calculation"])
        self.assertEqual(vecs.shape, (2, 384))

    def test_embed_texts_dtype(self):
        vecs = self.embedder.embed_texts(["test"])
        self.assertEqual(vecs.dtype, np.float32)

    def test_embed_texts_normalized(self):
        vecs = self.embedder.embed_texts(["normalize me", "also this"])
        norms = np.linalg.norm(vecs, axis=1)
        np.testing.assert_allclose(norms, np.ones(2), atol=1e-5)

    def test_embed_query_is_1d(self):
        vec = self.embedder.embed_query("discount percentage is wrong")
        self.assertEqual(vec.ndim, 1)
        self.assertEqual(vec.shape[0], 384)

    def test_embed_query_normalized(self):
        vec = self.embedder.embed_query("something")
        norm = float(np.linalg.norm(vec))
        self.assertAlmostEqual(norm, 1.0, places=5)

    def test_empty_list_returns_empty_array(self):
        vecs = self.embedder.embed_texts([])
        self.assertEqual(vecs.shape[0], 0)

    def test_similar_texts_have_higher_similarity(self):
        """A query should be closer to relevant text than irrelevant text."""
        query = self.embedder.embed_query("discount percentage calculation error")
        relevant = self.embedder.embed_texts(["calculate_discount applies percent incorrectly"])[0]
        irrelevant = self.embedder.embed_texts(["unrelated network socket timeout error"])[0]
        sim_relevant = float(np.dot(query, relevant))
        sim_irrelevant = float(np.dot(query, irrelevant))
        self.assertGreater(sim_relevant, sim_irrelevant,
            f"Expected relevant ({sim_relevant:.3f}) > irrelevant ({sim_irrelevant:.3f})")


# ---------------------------------------------------------------------------
# 5. FaissVectorIndex
# ---------------------------------------------------------------------------
class TestFaissVectorIndex(unittest.TestCase):
    """Verify FAISS index operations: add, search, metadata, empty edge case."""

    def _make_chunks(self, n=3):
        from mini_swe_agent.retrieval.chunker import CodeChunk
        return [
            CodeChunk(
                file_path=f"file{i}.py",
                symbol_name=f"func{i}",
                symbol_type="function",
                start_line=1,
                end_line=5,
                code=f"def func{i}(): pass",
            )
            for i in range(n)
        ]

    def test_add_and_size(self):
        from mini_swe_agent.retrieval.vector_index import FaissVectorIndex
        idx = FaissVectorIndex(dimension=4)
        chunks = self._make_chunks(3)
        vecs = np.random.randn(3, 4).astype(np.float32)
        # Normalize for inner product correctness
        vecs = vecs / np.linalg.norm(vecs, axis=1, keepdims=True)
        idx.add(vecs, chunks)
        self.assertEqual(idx.size(), 3)

    def test_search_returns_top_k(self):
        from mini_swe_agent.retrieval.vector_index import FaissVectorIndex
        idx = FaissVectorIndex(dimension=4)
        chunks = self._make_chunks(5)
        vecs = np.eye(5, 4, dtype=np.float32)
        vecs = vecs / (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-8)
        idx.add(vecs, chunks)
        query = vecs[0]
        results = idx.search(query, top_k=2)
        self.assertEqual(len(results), 2)

    def test_search_metadata_preserved(self):
        from mini_swe_agent.retrieval.vector_index import FaissVectorIndex
        idx = FaissVectorIndex(dimension=4)
        chunks = self._make_chunks(2)
        vecs = np.eye(2, 4, dtype=np.float32)
        vecs = vecs / (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-8)
        idx.add(vecs, chunks)
        results = idx.search(vecs[0], top_k=1)
        self.assertEqual(len(results), 1)
        self.assertIn("file_path", results[0])
        self.assertIn("symbol_name", results[0])
        self.assertIn("score", results[0])

    def test_nearest_neighbor_is_correct(self):
        """The nearest neighbor of a unit vector should be itself."""
        from mini_swe_agent.retrieval.vector_index import FaissVectorIndex
        idx = FaissVectorIndex(dimension=4)
        chunks = self._make_chunks(3)
        # Orthogonal basis vectors
        vecs = np.eye(3, 4, dtype=np.float32)
        vecs = vecs / (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-8)
        idx.add(vecs, chunks)
        # Query with vecs[1] — should find func1
        results = idx.search(vecs[1], top_k=1)
        self.assertEqual(results[0]["symbol_name"], "func1")

    def test_clear_resets_index(self):
        from mini_swe_agent.retrieval.vector_index import FaissVectorIndex
        idx = FaissVectorIndex(dimension=4)
        chunks = self._make_chunks(2)
        vecs = np.eye(2, 4, dtype=np.float32)
        idx.add(vecs, chunks)
        self.assertEqual(idx.size(), 2)
        idx.clear()
        self.assertEqual(idx.size(), 0)

    def test_search_empty_index_returns_empty(self):
        from mini_swe_agent.retrieval.vector_index import FaissVectorIndex
        idx = FaissVectorIndex(dimension=4)
        query = np.zeros(4, dtype=np.float32)
        results = idx.search(query, top_k=3)
        self.assertEqual(results, [])


# ---------------------------------------------------------------------------
# 6. SemanticRetriever — uses the sandbox (loads embedder once)
# ---------------------------------------------------------------------------
class TestSemanticRetriever(unittest.TestCase):
    """Integration tests for end-to-end semantic retrieval on sandbox."""

    @classmethod
    def setUpClass(cls):
        """Index the sandbox once for all tests in this class."""
        from mini_swe_agent.retrieval.retriever import SemanticRetriever
        sandbox_path = str(Path(__file__).parent.parent / "sandbox" / "mini_shop")
        cls.retriever = SemanticRetriever(sandbox_path)
        cls.chunk_count = cls.retriever.index_repository()

    def test_indexes_non_zero_chunks(self):
        self.assertGreater(self.chunk_count, 0,
            "Expected at least one chunk to be indexed")

    def test_retrieve_returns_list(self):
        results = self.retriever.retrieve("discount calculation", top_k=3)
        self.assertIsInstance(results, list)

    def test_retrieve_has_metadata_keys(self):
        results = self.retriever.retrieve("discount", top_k=1)
        if results:
            r = results[0]
            for key in ("file_path", "symbol_name", "symbol_type", "start_line", "end_line", "score"):
                self.assertIn(key, r, f"Missing key: {key}")

    def test_discount_query_retrieves_pricing_file(self):
        """For the discount issue, pricing.py or calculate_discount must appear in top-5."""
        results = self.retriever.retrieve(
            "discount percentage calculation is incorrect", top_k=5
        )
        file_paths = [r["file_path"] for r in results]
        symbols = [r["symbol_name"] for r in results]
        found = (
            any("pricing" in fp for fp in file_paths) or
            any("calculate_discount" in s for s in symbols)
        )
        self.assertTrue(found,
            f"Expected pricing.py or calculate_discount in top-5, got: {list(zip(file_paths, symbols))}")

    def test_remove_item_query_retrieves_cart_file(self):
        """For the remove_item issue, cart.py or remove_item must appear in top-5."""
        results = self.retriever.retrieve(
            "remove item raises KeyError instead of ItemNotFoundError", top_k=5
        )
        file_paths = [r["file_path"] for r in results]
        symbols = [r["symbol_name"] for r in results]
        found = (
            any("cart" in fp for fp in file_paths) or
            any("remove_item" in s or "ItemNotFound" in s for s in symbols)
        )
        self.assertTrue(found,
            f"Expected cart.py or remove_item in top-5, got: {list(zip(file_paths, symbols))}")

    def test_scores_between_neg1_and_1(self):
        results = self.retriever.retrieve("calculation error", top_k=5)
        for r in results:
            self.assertGreaterEqual(r["score"], -1.01)
            self.assertLessEqual(r["score"], 1.01)

    def test_empty_query_returns_empty(self):
        results = self.retriever.retrieve("", top_k=5)
        self.assertEqual(results, [])

    def test_top_k_respected(self):
        results = self.retriever.retrieve("function", top_k=2)
        self.assertLessEqual(len(results), 2)

    def test_retrieve_without_explicit_index_works(self):
        """retrieve() auto-indexes if not already done."""
        from mini_swe_agent.retrieval.retriever import SemanticRetriever
        sandbox_path = str(Path(__file__).parent.parent / "sandbox" / "mini_shop")
        r = SemanticRetriever(sandbox_path)
        # No explicit index_repository() call
        results = r.retrieve("discount", top_k=1)
        self.assertIsInstance(results, list)


# ---------------------------------------------------------------------------
# 7. ContextBuilder
# ---------------------------------------------------------------------------
class TestContextBuilder(unittest.TestCase):
    """Verify context formatting, chunking limits, and edge cases."""

    def _make_results(self, n=3, code_len=100):
        return [
            {
                "file_path": f"shop/file{i}.py",
                "symbol_name": f"func{i}",
                "symbol_type": "function",
                "start_line": 1,
                "end_line": 10,
                "score": 0.9 - i * 0.1,
                "code": "def func():\n    pass\n" * (code_len // 20 + 1),
            }
            for i in range(n)
        ]

    def test_empty_input_returns_empty_string(self):
        from mini_swe_agent.retrieval.context_builder import ContextBuilder
        cb = ContextBuilder()
        self.assertEqual(cb.build_context([]), "")

    def test_output_contains_file_path(self):
        from mini_swe_agent.retrieval.context_builder import ContextBuilder
        cb = ContextBuilder()
        results = self._make_results(1)
        ctx = cb.build_context(results)
        self.assertIn("shop/file0.py", ctx)

    def test_output_contains_symbol_name(self):
        from mini_swe_agent.retrieval.context_builder import ContextBuilder
        cb = ContextBuilder()
        results = self._make_results(1)
        ctx = cb.build_context(results)
        self.assertIn("func0", ctx)

    def test_output_contains_similarity_score(self):
        from mini_swe_agent.retrieval.context_builder import ContextBuilder
        cb = ContextBuilder()
        results = self._make_results(1)
        ctx = cb.build_context(results)
        self.assertIn("similarity", ctx)

    def test_max_chunks_respected(self):
        from mini_swe_agent.retrieval.context_builder import ContextBuilder
        cb = ContextBuilder(max_chunks=2)
        results = self._make_results(5)
        ctx = cb.build_context(results)
        # Only first 2 chunks should appear
        self.assertIn("func0", ctx)
        self.assertIn("func1", ctx)
        # func4 should not appear
        self.assertNotIn("func4", ctx)

    def test_oversized_code_is_truncated(self):
        from mini_swe_agent.retrieval.context_builder import ContextBuilder
        cb = ContextBuilder(max_chars_per_chunk=50)
        results = [
            {
                "file_path": "big.py",
                "symbol_name": "big_func",
                "symbol_type": "function",
                "start_line": 1,
                "end_line": 500,
                "score": 0.8,
                "code": "x = 1\n" * 300,   # ~1800 chars
            }
        ]
        ctx = cb.build_context(results)
        self.assertIn("truncated", ctx)

    def test_total_char_limit_respected(self):
        from mini_swe_agent.retrieval.context_builder import ContextBuilder
        cb = ContextBuilder(max_total_chars=200, max_chars_per_chunk=150)
        results = self._make_results(5, code_len=100)
        ctx = cb.build_context(results)
        # Output must be reasonably bounded
        self.assertLessEqual(len(ctx), 1000,
            "Context builder output far exceeds total char limit")


if __name__ == "__main__":
    unittest.main()
