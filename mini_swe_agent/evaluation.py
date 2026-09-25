"""Evaluation framework for Stage 4.4 — Self-Debugging SWE Agent.

Provides deterministic task running, workspace isolation, and metric collection
to compare Baseline (no debug) vs Self-Debugging modes.
"""

import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from .agent import MiniSWEAgent
from .llm import BaseLLMClient


@dataclass
class EvalTask:
    """Defines a deterministic software engineering evaluation task."""
    name: str
    issue_description: str
    llm_client_factory: Callable[[], BaseLLMClient]


@dataclass
class EvalResult:
    """Structured result of an evaluation run."""
    task_name: str
    mode: str
    success: bool
    total_steps: int
    tool_call_count: int
    debug_attempts: int
    failure_analysis_invoked: bool
    final_failure_type: Optional[str]
    final_summary: str
    elapsed_time_sec: float


def _count_debug_attempts(steps) -> int:
    """Count steps where failure analysis diagnostic context was injected."""
    count = 0
    for step in steps:
        if step.tool == "run_command" and "DIAGNOSTIC CONTEXT" in step.observation:
            count += 1
    return count


def _extract_failure_type(steps) -> Optional[str]:
    """Extract the last failure type from diagnostic context, if present."""
    last_type = None
    for step in steps:
        if step.tool == "run_command" and "DIAGNOSTIC CONTEXT" in step.observation:
            obs = step.observation
            # Look for "Failure Analysis: TYPE_NAME"
            marker = "Failure Analysis: "
            idx = obs.find(marker)
            if idx != -1:
                end = obs.find("\n", idx)
                raw = obs[idx + len(marker): end if end != -1 else idx + len(marker) + 40]
                last_type = raw.strip()
    return last_type


class EvaluationRunner:
    """Runs EvalTasks in isolated workspaces and collects metrics."""

    def __init__(self, source_sandbox_dir: str):
        if not os.path.isdir(source_sandbox_dir):
            raise ValueError(f"Sandbox directory '{source_sandbox_dir}' not found.")
        self.source_sandbox = source_sandbox_dir

    def run_task(self, task: EvalTask, mode: str, max_debug_attempts: int = 3) -> EvalResult:
        """
        Executes a task in an isolated copy of the sandbox.

        mode: 'baseline' disables self-debugging (max_debug_attempts=0).
              'self_debug' enables the Stage 4.3 retry loop.

        The source sandbox is never modified — all work happens inside a
        temporary directory that is cleaned up after each run.
        """
        if mode not in ["baseline", "self_debug"]:
            raise ValueError("mode must be 'baseline' or 'self_debug'")

        temp_dir = tempfile.mkdtemp(prefix="swe_eval_")
        workspace_dir = os.path.join(temp_dir, "workspace")

        try:
            # 1. Isolate workspace — copy sandbox into temp dir
            shutil.copytree(self.source_sandbox, workspace_dir)

            # 2. Configure agent based on mode
            agent_max_attempts = 0 if mode == "baseline" else max_debug_attempts
            llm_client = task.llm_client_factory()

            agent = MiniSWEAgent(
                workspace_dir=workspace_dir,
                llm_client=llm_client,
                max_debug_attempts=agent_max_attempts,
                verbose=False,
            )

            # 3. Execute
            start_time = time.time()
            result = agent.solve(task.issue_description)
            elapsed = time.time() - start_time

            # 4. Collect metrics
            debug_attempts = _count_debug_attempts(result.steps)
            failure_type = _extract_failure_type(result.steps)

            return EvalResult(
                task_name=task.name,
                mode=mode,
                success=result.success,
                total_steps=result.total_steps,
                tool_call_count=len(result.steps),
                debug_attempts=debug_attempts,
                failure_analysis_invoked=(debug_attempts > 0),
                final_failure_type=failure_type,
                final_summary=result.summary,
                elapsed_time_sec=elapsed,
            )
        finally:
            # 5. Always clean up — never leave temp dirs behind
            shutil.rmtree(temp_dir, ignore_errors=True)


def format_comparison_table(
    results: List[EvalResult],
) -> str:
    """
    Format a comparison table for a list of (baseline, self_debug) result pairs.

    Results should be ordered as [baseline_1, selfdebug_1, baseline_2, selfdebug_2, ...].
    """
    header = (
        f"{'Task':<28} {'Baseline':<10} {'Self-Debug':<12} "
        f"{'Debug Attempts':<16} {'FA Invoked':<12} {'Final Failure Type'}"
    )
    sep = "-" * 95
    rows = [header, sep]

    # Pair them up by task name
    by_task: dict = {}
    for r in results:
        by_task.setdefault(r.task_name, {})[r.mode] = r

    for task_name, modes in by_task.items():
        base = modes.get("baseline")
        sd = modes.get("self_debug")
        base_str = ("PASS" if base.success else "FAIL") if base else "N/A"
        sd_str = ("PASS" if sd.success else "FAIL") if sd else "N/A"
        attempts = sd.debug_attempts if sd else 0
        fa = ("YES" if sd.failure_analysis_invoked else "NO") if sd else "N/A"
        ft = (sd.final_failure_type or "—") if sd else "—"
        rows.append(
            f"{task_name:<28} {base_str:<10} {sd_str:<12} {attempts:<16} {fa:<12} {ft}"
        )

    rows.append(sep)
    return "\n".join(rows)
