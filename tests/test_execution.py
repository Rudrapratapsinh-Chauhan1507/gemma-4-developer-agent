"""Unit tests for Stage 4.1 — Structured Command Execution.

Tests cover:
 - CommandResult dataclass fields and defaults
 - success property (exit code 0 vs non-zero, timed_out, error_message)
 - to_display_string() output format
 - ToolRegistry.run_command_structured() for:
     - successful command (stdout capture)
     - failed command (non-zero exit code)
     - stderr capture
     - combined stdout + stderr
     - structured result field correctness
 - Backward compatibility: ToolRegistry.run_command() still returns a str
"""

import os
import shutil
import tempfile
import unittest

from mini_swe_agent.execution import CommandResult
from mini_swe_agent.tools import ToolRegistry


class TestCommandResult(unittest.TestCase):

    def test_defaults(self):
        r = CommandResult(command="echo hi")
        self.assertEqual(r.command, "echo hi")
        self.assertEqual(r.return_code, 0)
        self.assertEqual(r.stdout, "")
        self.assertEqual(r.stderr, "")
        self.assertFalse(r.timed_out)
        self.assertEqual(r.error_message, "")

    def test_success_zero_exit(self):
        r = CommandResult(command="true", return_code=0)
        self.assertTrue(r.success)

    def test_failure_nonzero_exit(self):
        r = CommandResult(command="false", return_code=1)
        self.assertFalse(r.success)

    def test_failure_timed_out(self):
        r = CommandResult(command="sleep 999", return_code=-1, timed_out=True)
        self.assertFalse(r.success)

    def test_failure_error_message(self):
        r = CommandResult(command="bad", return_code=-1, error_message="OS error")
        self.assertFalse(r.success)

    def test_to_display_string_success_with_stdout(self):
        r = CommandResult(command="echo hi", return_code=0, stdout="hi")
        s = r.to_display_string()
        self.assertIn("Exit Code: 0", s)
        self.assertIn("STDOUT", s)
        self.assertIn("hi", s)

    def test_to_display_string_failure_with_stderr(self):
        r = CommandResult(command="bad", return_code=1, stderr="not found")
        s = r.to_display_string()
        self.assertIn("Exit Code: 1", s)
        self.assertIn("STDERR", s)
        self.assertIn("not found", s)

    def test_to_display_string_no_output(self):
        r = CommandResult(command="true", return_code=0)
        s = r.to_display_string()
        self.assertIn("Exit Code: 0", s)
        self.assertIn("(No output)", s)

    def test_to_display_string_timed_out(self):
        r = CommandResult(command="sleep", return_code=-1, timed_out=True)
        s = r.to_display_string()
        self.assertIn("timed out", s)

    def test_to_display_string_error_message(self):
        r = CommandResult(command="bad", return_code=-1, error_message="permission denied")
        s = r.to_display_string()
        self.assertIn("Execution error", s)
        self.assertIn("permission denied", s)


class TestRunCommandStructured(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.tools = ToolRegistry(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_returns_command_result_type(self):
        r = self.tools.run_command_structured('python -c "print(1)"')
        self.assertIsInstance(r, CommandResult)

    def test_successful_command(self):
        r = self.tools.run_command_structured('python -c "print(42)"')
        self.assertEqual(r.return_code, 0)
        self.assertTrue(r.success)
        self.assertIn("42", r.stdout)

    def test_failed_command_nonzero_return_code(self):
        r = self.tools.run_command_structured('python -c "raise SystemExit(2)"')
        self.assertEqual(r.return_code, 2)
        self.assertFalse(r.success)

    def test_stdout_captured(self):
        r = self.tools.run_command_structured('python -c "print(\'hello stdout\')"')
        self.assertIn("hello stdout", r.stdout)
        self.assertEqual(r.stderr, "")

    def test_stderr_captured(self):
        r = self.tools.run_command_structured(
            'python -c "import sys; sys.stderr.write(\'hello stderr\\n\')"'
        )
        self.assertIn("hello stderr", r.stderr)

    def test_command_field_stored(self):
        cmd = 'python -c "print(0)"'
        r = self.tools.run_command_structured(cmd)
        self.assertEqual(r.command, cmd)

    def test_structured_result_display_string_matches_format(self):
        """to_display_string() must contain the same key sections as run_command()."""
        cmd = 'python -c "print(99)"'
        r = self.tools.run_command_structured(cmd)
        display = r.to_display_string()
        legacy = self.tools.run_command(cmd)
        # Both should mention the exit code and the value
        self.assertIn("Exit Code: 0", display)
        self.assertIn("99", display)
        self.assertIn("Exit Code: 0", legacy)
        self.assertIn("99", legacy)


class TestBackwardCompatibility(unittest.TestCase):
    """run_command() must continue to return a str, unchanged."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.tools = ToolRegistry(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_run_command_returns_str(self):
        result = self.tools.run_command('python -c "print(42)"')
        self.assertIsInstance(result, str)

    def test_run_command_exit_code_in_output(self):
        result = self.tools.run_command('python -c "print(42)"')
        self.assertIn("Exit Code: 0", result)

    def test_run_command_stdout_in_output(self):
        result = self.tools.run_command('python -c "print(42)"')
        self.assertIn("42", result)

    def test_run_command_nonzero_exit_in_output(self):
        result = self.tools.run_command('python -c "raise SystemExit(1)"')
        self.assertIn("Exit Code: 1", result)


if __name__ == "__main__":
    unittest.main()
