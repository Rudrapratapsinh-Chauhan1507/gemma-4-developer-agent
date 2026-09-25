"""Structured command execution result for Stage 4 — Self-Debugging SWE Agent.

Provides a clean, inspectable representation of command/test execution outcomes.
Future Stage 4 components (e.g., failure analysis, traceback parsing, retry logic)
should consume CommandResult rather than parsing raw string output.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CommandResult:
    """Structured result of a shell command execution.

    Attributes:
        command:          The exact command string that was executed.
        return_code:      The process exit code (0 = success, non-zero = failure).
        stdout:           Captured standard output (stripped). Empty string if none.
        stderr:           Captured standard error (stripped). Empty string if none.
        timed_out:        True if the process was killed due to a timeout.
        error_message:    Non-empty only when an unexpected exception prevented
                          the process from starting (e.g., permission denied).
    """

    command: str
    return_code: int = 0
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    error_message: str = ""

    @property
    def success(self) -> bool:
        """True when the command exited with return code 0 and did not time out."""
        return self.return_code == 0 and not self.timed_out and not self.error_message

    def to_display_string(self) -> str:
        """Render a human-readable / LLM-consumable string matching the
        existing run_command format so results can be reused in both contexts.
        """
        if self.error_message:
            return f"Execution error: {self.error_message}"
        if self.timed_out:
            return (
                f"Error: Command timed out. "
                f"Exit Code: {self.return_code}"
            )

        lines = [f"Exit Code: {self.return_code}"]
        if self.stdout:
            lines.append("--- STDOUT ---")
            lines.append(self.stdout)
        if self.stderr:
            lines.append("--- STDERR ---")
            lines.append(self.stderr)
        if not self.stdout and not self.stderr:
            lines.append("(No output)")
        return "\n".join(lines)
