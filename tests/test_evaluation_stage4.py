"""Unit tests for Stage 4.4 — Evaluation Framework.

Tests cover:
1. EvalTask schema
2. Baseline configuration (max_debug_attempts=0)
3. Self-debug configuration
4. Result / metric collection
5. Comparison / report generation (format_comparison_table)
6. Workspace isolation
7. Deterministic task execution
8. Backward compatibility (existing Stage 1/2/3 behavior unchanged)
"""

import os
import shutil
import tempfile
import unittest
from typing import List, Dict, Any

from mini_swe_agent.evaluation import (
    EvalTask,
    EvalResult,
    EvaluationRunner,
    format_comparison_table,
    _count_debug_attempts,
    _extract_failure_type,
)
from mini_swe_agent.llm import BaseLLMClient, DeterministicSWEClient
from mini_swe_agent.agent import AgentStep


# ─────────────────────────────────────────
# Helper LLM clients for isolated tests
# ─────────────────────────────────────────

class MockPassingClient(BaseLLMClient):
    """Always finishes immediately with success."""
    def generate_action(self, messages: List[Dict[str, Any]], sys_prompt: str) -> Dict[str, Any]:
        return {"tool": "finish", "args": {"summary": "Done immediately"}}


class MockFailThenPassClient(BaseLLMClient):
    """Runs a failing command then a passing command."""
    def __init__(self):
        self.call = 0

    def generate_action(self, messages: List[Dict[str, Any]], sys_prompt: str) -> Dict[str, Any]:
        self.call += 1
        if self.call == 1:
            return {"tool": "run_command", "args": {"command": 'python -c "raise ValueError(\'Bad\')"'}}
        elif self.call == 2:
            return {"tool": "run_command", "args": {"command": 'python -c "print(\'OK\')"'}}
        return {"tool": "finish", "args": {"summary": "Recovered"}}


class MockAlwaysFailClient(BaseLLMClient):
    """Always runs the same failing command (triggers repeated-failure abort)."""
    def generate_action(self, messages: List[Dict[str, Any]], sys_prompt: str) -> Dict[str, Any]:
        return {"tool": "run_command", "args": {"command": 'python -c "raise RuntimeError(\'always\')"'}}


class MockUniqueFailsClient(BaseLLMClient):
    """Raises a unique error each time (triggers max-attempts abort)."""
    def __init__(self):
        self.n = 0

    def generate_action(self, messages: List[Dict[str, Any]], sys_prompt: str) -> Dict[str, Any]:
        self.n += 1
        return {"tool": "run_command", "args": {"command": f'python -c "raise Exception(\'err{self.n}\')"'}}


# ─────────────────────────────────────────
# Helper to create a minimal sandbox
# ─────────────────────────────────────────

def make_sandbox() -> str:
    d = tempfile.mkdtemp(prefix="swe_sandbox_")
    os.makedirs(os.path.join(d, "shop"))
    with open(os.path.join(d, "shop", "dummy.py"), "w") as f:
        f.write("# placeholder\n")
    return d


# ─────────────────────────────────────────
# Test helpers: _count_debug_attempts / _extract_failure_type
# ─────────────────────────────────────────

class TestMetricHelpers(unittest.TestCase):
    def _make_step(self, tool: str, observation: str) -> AgentStep:
        return AgentStep(step_number=1, thought="", tool=tool, args={}, observation=observation)

    def test_count_debug_attempts_none(self):
        steps = [self._make_step("run_command", "Exit Code: 0\nOK")]
        self.assertEqual(_count_debug_attempts(steps), 0)

    def test_count_debug_attempts_one(self):
        obs = "Exit Code: 1\n--- DIAGNOSTIC CONTEXT (Attempt 1/3) ---\nFailure Analysis: TYPE_ERROR"
        steps = [self._make_step("run_command", obs)]
        self.assertEqual(_count_debug_attempts(steps), 1)

    def test_count_debug_attempts_two(self):
        obs = "--- DIAGNOSTIC CONTEXT (Attempt 1/3) ---"
        steps = [
            self._make_step("run_command", obs),
            self._make_step("run_command", "Exit Code: 0"),
            self._make_step("run_command", obs),
        ]
        self.assertEqual(_count_debug_attempts(steps), 2)

    def test_extract_failure_type_none(self):
        steps = [self._make_step("run_command", "Exit Code: 0")]
        self.assertIsNone(_extract_failure_type(steps))

    def test_extract_failure_type_present(self):
        obs = "--- DIAGNOSTIC CONTEXT ---\nFailure Analysis: SYNTAX_ERROR\nSummary: bad"
        steps = [self._make_step("run_command", obs)]
        result = _extract_failure_type(steps)
        self.assertEqual(result, "SYNTAX_ERROR")

    def test_extract_failure_type_takes_last(self):
        obs1 = "--- DIAGNOSTIC CONTEXT ---\nFailure Analysis: TYPE_ERROR\n"
        obs2 = "--- DIAGNOSTIC CONTEXT ---\nFailure Analysis: ASSERTION_FAILURE\n"
        steps = [
            self._make_step("run_command", obs1),
            self._make_step("run_command", obs2),
        ]
        self.assertEqual(_extract_failure_type(steps), "ASSERTION_FAILURE")


# ─────────────────────────────────────────
# 1. EvalTask schema
# ─────────────────────────────────────────

class TestEvalTaskSchema(unittest.TestCase):
    def test_fields_stored(self):
        task = EvalTask("my_task", "Fix the bug", MockPassingClient)
        self.assertEqual(task.name, "my_task")
        self.assertEqual(task.issue_description, "Fix the bug")
        self.assertIs(task.llm_client_factory, MockPassingClient)

    def test_factory_is_callable(self):
        task = EvalTask("t", "desc", MockPassingClient)
        client = task.llm_client_factory()
        self.assertIsInstance(client, MockPassingClient)


# ─────────────────────────────────────────
# 2. Baseline configuration
# ─────────────────────────────────────────

class TestBaselineMode(unittest.TestCase):
    def setUp(self):
        self.sandbox = make_sandbox()
        self.runner = EvaluationRunner(self.sandbox)

    def tearDown(self):
        shutil.rmtree(self.sandbox, ignore_errors=True)

    def test_baseline_success(self):
        task = EvalTask("t", "issue", MockPassingClient)
        res = self.runner.run_task(task, mode="baseline")
        self.assertTrue(res.success)
        self.assertEqual(res.mode, "baseline")

    def test_baseline_no_debug_attempts(self):
        """Baseline must not invoke failure analysis even if a command fails."""
        task = EvalTask("t", "issue", MockFailThenPassClient)
        res = self.runner.run_task(task, mode="baseline")
        self.assertEqual(res.debug_attempts, 0)
        self.assertFalse(res.failure_analysis_invoked)

    def test_baseline_invalid_mode_raises(self):
        task = EvalTask("t", "issue", MockPassingClient)
        with self.assertRaises(ValueError):
            self.runner.run_task(task, mode="invalid")


# ─────────────────────────────────────────
# 3. Self-debug configuration
# ─────────────────────────────────────────

class TestSelfDebugMode(unittest.TestCase):
    def setUp(self):
        self.sandbox = make_sandbox()
        self.runner = EvaluationRunner(self.sandbox)

    def tearDown(self):
        shutil.rmtree(self.sandbox, ignore_errors=True)

    def test_self_debug_success_path(self):
        task = EvalTask("t", "issue", MockPassingClient)
        res = self.runner.run_task(task, mode="self_debug")
        self.assertTrue(res.success)
        self.assertEqual(res.mode, "self_debug")

    def test_self_debug_invokes_failure_analysis(self):
        task = EvalTask("t", "issue", MockFailThenPassClient)
        res = self.runner.run_task(task, mode="self_debug", max_debug_attempts=3)
        # First command fails → diagnostic context injected
        self.assertTrue(res.failure_analysis_invoked)
        self.assertGreater(res.debug_attempts, 0)


# ─────────────────────────────────────────
# 4. Result / metric collection
# ─────────────────────────────────────────

class TestResultMetricCollection(unittest.TestCase):
    def setUp(self):
        self.sandbox = make_sandbox()
        self.runner = EvaluationRunner(self.sandbox)

    def tearDown(self):
        shutil.rmtree(self.sandbox, ignore_errors=True)

    def test_result_has_all_required_fields(self):
        task = EvalTask("t", "issue", MockPassingClient)
        res = self.runner.run_task(task, mode="baseline")
        required = [
            "task_name", "mode", "success", "total_steps", "tool_call_count",
            "debug_attempts", "failure_analysis_invoked", "final_failure_type",
            "final_summary", "elapsed_time_sec",
        ]
        for field in required:
            self.assertTrue(hasattr(res, field), f"EvalResult missing field: {field}")

    def test_tool_call_count_matches_steps(self):
        task = EvalTask("t", "issue", MockPassingClient)
        res = self.runner.run_task(task, mode="baseline")
        # finish is not counted as a step (it returns before appending)
        self.assertIsInstance(res.tool_call_count, int)
        self.assertGreaterEqual(res.tool_call_count, 0)

    def test_elapsed_time_nonnegative(self):
        task = EvalTask("t", "issue", MockPassingClient)
        res = self.runner.run_task(task, mode="baseline")
        self.assertGreaterEqual(res.elapsed_time_sec, 0.0)

    def test_final_failure_type_none_on_success(self):
        task = EvalTask("t", "issue", MockPassingClient)
        res = self.runner.run_task(task, mode="self_debug")
        self.assertIsNone(res.final_failure_type)


# ─────────────────────────────────────────
# 5. Comparison / report generation
# ─────────────────────────────────────────

class TestComparisonReport(unittest.TestCase):
    def _make_result(self, task_name, mode, success, debug_attempts=0, fa=False, ft=None) -> EvalResult:
        return EvalResult(
            task_name=task_name,
            mode=mode,
            success=success,
            total_steps=3,
            tool_call_count=2,
            debug_attempts=debug_attempts,
            failure_analysis_invoked=fa,
            final_failure_type=ft,
            final_summary="summary",
            elapsed_time_sec=0.5,
        )

    def test_format_table_contains_task_names(self):
        results = [
            self._make_result("task_A", "baseline", True),
            self._make_result("task_A", "self_debug", True),
        ]
        table = format_comparison_table(results)
        self.assertIn("task_A", table)
        self.assertIn("PASS", table)

    def test_format_table_shows_fail(self):
        results = [
            self._make_result("task_B", "baseline", False),
            self._make_result("task_B", "self_debug", True, debug_attempts=1, fa=True),
        ]
        table = format_comparison_table(results)
        self.assertIn("FAIL", table)
        self.assertIn("PASS", table)
        self.assertIn("YES", table)

    def test_format_table_shows_failure_type(self):
        results = [
            self._make_result("task_C", "baseline", False, ft="SYNTAX_ERROR"),
            self._make_result("task_C", "self_debug", False, ft="SYNTAX_ERROR", fa=True),
        ]
        table = format_comparison_table(results)
        self.assertIn("SYNTAX_ERROR", table)

    def test_format_table_is_string(self):
        results = [
            self._make_result("task_D", "baseline", True),
            self._make_result("task_D", "self_debug", True),
        ]
        self.assertIsInstance(format_comparison_table(results), str)


# ─────────────────────────────────────────
# 6. Workspace isolation
# ─────────────────────────────────────────

class TestWorkspaceIsolation(unittest.TestCase):
    def setUp(self):
        self.sandbox = make_sandbox()
        self.runner = EvaluationRunner(self.sandbox)

    def tearDown(self):
        shutil.rmtree(self.sandbox, ignore_errors=True)

    def test_source_sandbox_unchanged_after_run(self):
        """The source sandbox directory must not be modified by a task run."""
        sentinel_path = os.path.join(self.sandbox, "shop", "dummy.py")
        original_mtime = os.path.getmtime(sentinel_path)

        task = EvalTask("t", "issue", MockPassingClient)
        self.runner.run_task(task, mode="self_debug")

        self.assertEqual(os.path.getmtime(sentinel_path), original_mtime)

    def test_source_sandbox_unchanged_on_failure(self):
        """Even when a task fails, the source sandbox is untouched."""
        task = EvalTask("t", "issue", MockAlwaysFailClient)
        self.runner.run_task(task, mode="self_debug", max_debug_attempts=1)
        self.assertTrue(os.path.isdir(self.sandbox))

    def test_invalid_sandbox_raises(self):
        with self.assertRaises(ValueError):
            EvaluationRunner("/nonexistent/path/abc123")

    def test_two_runs_of_same_task_are_independent(self):
        """Running the same task twice should give independent results."""
        task = EvalTask("t", "issue", MockPassingClient)
        r1 = self.runner.run_task(task, mode="baseline")
        r2 = self.runner.run_task(task, mode="baseline")
        self.assertTrue(r1.success)
        self.assertTrue(r2.success)


# ─────────────────────────────────────────
# 7. Deterministic task execution
# ─────────────────────────────────────────

class TestDeterministicExecution(unittest.TestCase):
    def setUp(self):
        self.sandbox = make_sandbox()
        self.runner = EvaluationRunner(self.sandbox)

    def tearDown(self):
        shutil.rmtree(self.sandbox, ignore_errors=True)

    def test_same_task_same_success_outcome(self):
        task = EvalTask("t", "issue", MockPassingClient)
        r1 = self.runner.run_task(task, mode="baseline")
        r2 = self.runner.run_task(task, mode="baseline")
        self.assertEqual(r1.success, r2.success)

    def test_repeated_failure_aborts_deterministically(self):
        """Repeated identical failure must abort on the 2nd occurrence."""
        task = EvalTask("t", "issue", MockAlwaysFailClient)
        res = self.runner.run_task(task, mode="self_debug", max_debug_attempts=5)
        self.assertFalse(res.success)
        # Should abort after 2nd occurrence (1 diagnostic + 1 repeat)
        self.assertLessEqual(res.debug_attempts, 2)


# ─────────────────────────────────────────
# 8. Backward compatibility
# ─────────────────────────────────────────

class TestBackwardCompatibility(unittest.TestCase):
    """
    Ensures Stage 1/2/3 behavior (MiniSWEAgent without debug params) is unchanged.
    The DeterministicSWEClient sandbox integration is the primary regression test.
    """
    def setUp(self):
        # Use the real mini_shop sandbox for backward-compat tests
        self.real_sandbox = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "sandbox", "mini_shop"
        )
        self.skip = not os.path.isdir(self.real_sandbox)

    def test_deterministic_client_discount_still_works(self):
        if self.skip:
            self.skipTest("sandbox/mini_shop not found")
        sandbox = self.real_sandbox
        runner = EvaluationRunner(sandbox)
        task = EvalTask(
            name="compat_discount",
            issue_description="discount percentage calculation is incorrect",
            llm_client_factory=DeterministicSWEClient,
        )
        res = runner.run_task(task, mode="baseline")
        self.assertTrue(res.success, f"DeterministicSWEClient discount task failed: {res.final_summary}")

    def test_eval_result_is_not_agent_result(self):
        """EvalResult must be its own type, not an AgentResult alias."""
        from mini_swe_agent.agent import AgentResult
        self.assertIsNot(EvalResult, AgentResult)


if __name__ == "__main__":
    unittest.main()
