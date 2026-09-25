"""Unit tests for Stage 4.2 — Failure Analysis and Code Localization."""

import unittest
from mini_swe_agent.execution import CommandResult
from mini_swe_agent.tools import ToolRegistry
from mini_swe_agent.failure_analysis import FailureAnalyzer, FailureAnalysis

class DummyRetriever:
    def retrieve(self, query, top_k):
        return [{"file_path": "dummy_retrieved.py", "symbol_name": "retrieved_symbol"}]

class DummyGraph:
    def has_node(self, node_id):
        return True

class TestFailureAnalyzer(unittest.TestCase):
    def setUp(self):
        self.tools = ToolRegistry(".")
        self.analyzer = FailureAnalyzer(self.tools)

    def test_successful_command(self):
        result = CommandResult(command="echo OK", return_code=0, stdout="OK")
        analysis = self.analyzer.analyze(result)
        self.assertFalse(analysis.failed)
        self.assertEqual(analysis.failure_type, "success")
        self.assertEqual(analysis.candidate_files, [])
        self.assertEqual(analysis.candidate_symbols, [])

    def test_syntax_error(self):
        stderr = '  File "shop/cart.py", line 10\n    def remove_item(self)\n                       ^\nSyntaxError: expected \':\''
        result = CommandResult(command="python test.py", return_code=1, stderr=stderr)
        analysis = self.analyzer.analyze(result)

        self.assertTrue(analysis.failed)
        self.assertEqual(analysis.failure_type, "syntax_error")
        self.assertEqual(analysis.evidence["source_file"], "shop/cart.py")
        self.assertEqual(analysis.evidence["line_number"], "10")
        self.assertEqual(analysis.evidence["error_message"], "SyntaxError: expected ':'")
        self.assertIn("shop/cart.py", analysis.candidate_files)

    def test_assertion_failure_pytest(self):
        stdout = """
=================================== FAILURES ===================================
_______________________ TestShoppingCart.test_total ________________________
FAILED tests/test_cart.py::TestShoppingCart::test_total - AssertionError: assert 10 == 20
        """
        result = CommandResult(command="pytest", return_code=1, stdout=stdout)
        analysis = self.analyzer.analyze(result)

        self.assertTrue(analysis.failed)
        self.assertEqual(analysis.failure_type, "assertion_failure")
        self.assertEqual(analysis.evidence["test_file"], "tests/test_cart.py")
        self.assertEqual(analysis.evidence["test_name"], "test_total")
        self.assertIn("tests/test_cart.py", analysis.candidate_files)
        self.assertIn("test_total", analysis.candidate_symbols)

    def test_type_error_traceback(self):
        stderr = """Traceback (most recent call last):
  File "main.py", line 5, in <module>
    process()
  File "utils.py", line 12, in process
    return x + "1"
TypeError: unsupported operand type(s) for +: 'int' and 'str'
"""
        result = CommandResult(command="python main.py", return_code=1, stderr=stderr)
        analysis = self.analyzer.analyze(result)

        self.assertTrue(analysis.failed)
        self.assertEqual(analysis.failure_type, "type_error")
        self.assertEqual(analysis.evidence["source_file"], "utils.py")
        self.assertEqual(analysis.evidence["line_number"], "12")
        self.assertEqual(analysis.evidence["test_name"], "process")
        self.assertEqual(analysis.evidence["error_message"], "TypeError: unsupported operand type(s) for +: 'int' and 'str'")
        self.assertIn("utils.py", analysis.candidate_files)
        self.assertIn("process", analysis.candidate_symbols)

    def test_timeout(self):
        result = CommandResult(command="sleep 10", return_code=-1, timed_out=True)
        analysis = self.analyzer.analyze(result)
        self.assertTrue(analysis.failed)
        self.assertEqual(analysis.failure_type, "timeout")

    def test_unknown_failure(self):
        result = CommandResult(command="custom_tool", return_code=1, stdout="It broke.")
        analysis = self.analyzer.analyze(result)
        self.assertTrue(analysis.failed)
        self.assertEqual(analysis.failure_type, "unknown_failure")

    def test_semantic_retrieval_integration(self):
        self.tools.retriever = DummyRetriever()
        stderr = "Exception: Something failed in retrieval test"
        result = CommandResult(command="test", return_code=1, stderr=stderr)
        analysis = self.analyzer.analyze(result)

        self.assertIn("dummy_retrieved.py", analysis.candidate_files)
        self.assertIn("retrieved_symbol", analysis.candidate_symbols)

    def test_code_graph_integration(self):
        # Setup graph mock indirectly via overriding the enrich_with_graph or passing actual graph.
        # Since testing with actual graph requires building it, we'll just check that it handles
        # missing graph gracefully (which it does because self.tools.code_graph is None).
        result = CommandResult(command="test", return_code=1, stderr="Exception: err")
        analysis = self.analyzer.analyze(result)
        self.assertEqual(analysis.candidate_files, [])

    def test_tool_registry_analyze_failure(self):
        stderr = "NameError: name 'foo' is not defined"
        output = self.tools.analyze_failure(command="python script.py", return_code=1, stdout="", stderr=stderr)
        self.assertIn("Failure Analysis: NAME_ERROR", output)
        self.assertIn("NameError: name 'foo' is not defined", output)

    def test_tool_registry_execute_analyze_failure(self):
        stderr = "NameError: name 'foo' is not defined"
        output = self.tools.execute("analyze_failure", {
            "command": "python script.py",
            "return_code": 1,
            "stdout": "",
            "stderr": stderr
        })
        self.assertIn("Failure Analysis: NAME_ERROR", output)

if __name__ == "__main__":
    unittest.main()
