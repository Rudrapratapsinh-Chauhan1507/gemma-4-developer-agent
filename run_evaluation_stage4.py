"""Stage 4.4 Evaluation Runner — Self-Debugging SWE Agent Benchmark.

Compares Baseline (self-debugging disabled) vs Self-Debug (Stage 4.3 retry loop)
on four deterministic mini_shop tasks.

Usage:
    python run_evaluation_stage4.py
"""

import os
import sys

from mini_swe_agent.evaluation import (
    EvalTask,
    EvalResult,
    EvaluationRunner,
    format_comparison_table,
)
from mini_swe_agent.llm import DeterministicSWEClient, BaseLLMClient


# ──────────────────────────────────────────────────────────────────────────────
# Deterministic LLM clients for evaluation scenarios
# ──────────────────────────────────────────────────────────────────────────────

class RecoverableBugClient(BaseLLMClient):
    """
    Task 2: Simulates an agent that introduces a syntax error on its first edit,
    receives a DIAGNOSTIC CONTEXT observation, then corrects the error and passes.

    Baseline (no diagnostic context): finishes with a "gave up" message.
    Self-debug: observes diagnostic context, fixes the edit, passes.
    """
    def __init__(self):
        self.state = 0

    def generate_action(self, messages, sys_prompt):
        last_obs = messages[-1]["content"] if messages else ""
        if self.state == 0:
            self.state = 1
            # Introduce a syntax error intentionally
            return {
                "tool": "edit_file",
                "args": {
                    "path": "shop/pricing.py",
                    "target_string": "    return round(total - discount_amount, 2)",
                    "replacement_string": "    return round(total - discount_amount, 2) + ",
                },
            }
        elif self.state == 1:
            self.state = 2
            return {"tool": "run_command", "args": {"command": "python -m unittest tests/test_cart.py"}}
        elif self.state == 2:
            if "DIAGNOSTIC CONTEXT" in last_obs:
                # Self-debug path: fix the bad edit
                self.state = 3
                return {
                    "tool": "edit_file",
                    "args": {
                        "path": "shop/pricing.py",
                        "target_string": "    return round(total - discount_amount, 2) + ",
                        "replacement_string": "    return round(total - discount_amount, 2)",
                    },
                }
            else:
                # Baseline path: no diagnostic — give up
                return {"tool": "finish", "args": {"summary": "Gave up — no diagnostic context available"}}
        elif self.state == 3:
            self.state = 4
            return {"tool": "run_command", "args": {"command": "python -m unittest tests/test_cart.py"}}
        else:
            return {"tool": "finish", "args": {"summary": "Recovered: syntax error corrected, tests pass"}}


class RepeatedFailureClient(BaseLLMClient):
    """
    Task 3: Simulates an agent stuck running the same failing command on every step.
    The self-debug loop should detect the repeated failure signature and abort early.
    """
    def generate_action(self, messages, sys_prompt):
        return {
            "tool": "run_command",
            "args": {"command": "python -m unittest tests/test_cart.py -k test_discount_calculation"},
        }


class MaxAttemptsClient(BaseLLMClient):
    """
    Task 4: Simulates an agent that makes a unique (different) error each attempt,
    so it cannot be short-circuited by repeated-failure detection, but hits the
    max_debug_attempts ceiling.
    """
    def __init__(self):
        self.attempt = 0

    def generate_action(self, messages, sys_prompt):
        self.attempt += 1
        return {
            "tool": "run_command",
            "args": {"command": f'python -c "raise Exception(\'Unique Error {self.attempt}\')"'},
        }


# ──────────────────────────────────────────────────────────────────────────────
# Task registry
# ──────────────────────────────────────────────────────────────────────────────

TASKS = [
    EvalTask(
        name="task_1_first_try_success",
        issue_description="discount percentage calculation is incorrect",
        llm_client_factory=DeterministicSWEClient,
    ),
    EvalTask(
        name="task_2_recoverable",
        issue_description="Fix discount logic",
        llm_client_factory=RecoverableBugClient,
    ),
    EvalTask(
        name="task_3_repeated_fail",
        issue_description="discount calculation fails",
        llm_client_factory=RepeatedFailureClient,
    ),
    EvalTask(
        name="task_4_max_attempts",
        issue_description="keep trying",
        llm_client_factory=MaxAttemptsClient,
    ),
]


# ──────────────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────────────

def run_evaluation(max_debug_attempts: int = 3) -> None:
    sandbox_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sandbox", "mini_shop")
    if not os.path.isdir(sandbox_dir):
        print(f"[ERROR] Sandbox not found at: {sandbox_dir}", file=sys.stderr)
        sys.exit(1)

    runner = EvaluationRunner(sandbox_dir)
    all_results: list[EvalResult] = []

    print(f"\nStage 4.4 — Evaluation ({len(TASKS)} tasks, max_debug_attempts={max_debug_attempts})")
    print("=" * 95)

    for task in TASKS:
        print(f"\n  Running: {task.name}")
        res_base = runner.run_task(task, mode="baseline")
        res_sd = runner.run_task(task, mode="self_debug", max_debug_attempts=max_debug_attempts)
        all_results.extend([res_base, res_sd])

        # Per-task diagnostics
        for res in [res_base, res_sd]:
            outcome = "PASS" if res.success else "FAIL"
            fa = "YES" if res.failure_analysis_invoked else "NO"
            ft = res.final_failure_type or "—"
            print(
                f"    [{res.mode:<10}] {outcome}  steps={res.total_steps}  "
                f"tool_calls={res.tool_call_count}  debug_attempts={res.debug_attempts}  "
                f"FA={fa}  failure_type={ft}  "
                f"time={res.elapsed_time_sec:.2f}s"
            )
            if not res.success:
                summary_short = res.final_summary[:80].replace("\n", " ")
                print(f"             summary: {summary_short}")

    print("\n" + format_comparison_table(all_results))
    print(
        "\nNOTE: Wall-clock time varies by machine and is not a primary correctness metric.\n"
        "NOTE: 'Baseline' mode sets max_debug_attempts=0 — self-debugging is disabled.\n"
        "NOTE: All tasks ran in isolated temporary workspaces; the original sandbox is unchanged.\n"
    )


if __name__ == "__main__":
    run_evaluation()
