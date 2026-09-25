"""Tests for Stage 4.3 — Self-Debugging Retry Loop."""

import os
import shutil
import tempfile
import unittest
from typing import List, Dict, Any

from mini_swe_agent.agent import MiniSWEAgent
from mini_swe_agent.llm import BaseLLMClient

class DebugLLMClient(BaseLLMClient):
    """A mock LLM client to simulate debugging scenarios."""

    def __init__(self, scenario: str):
        self.scenario = scenario
        self.call_count = 0

    def generate_action(self, messages: List[Dict[str, str]], system_prompt: str) -> Dict[str, Any]:
        self.call_count += 1

        last_obs = messages[-1]["content"] if messages and "Observation:" in messages[-1]["content"] else ""

        if self.scenario == "fail_then_succeed":
            if self.call_count == 1:
                # 1. Trigger a failing command
                return {
                    "thought": "I will run a command that fails.",
                    "tool": "run_command",
                    "args": {"command": 'python -c "raise ValueError(\'Bad\')"'}
                }
            elif self.call_count == 2:
                # 2. Check if diagnostic context is present, then finish
                if "DIAGNOSTIC CONTEXT (Attempt 1" in last_obs and "RUNTIME_ERROR" in last_obs:
                    return {
                        "thought": "I saw the diagnostic context and will now succeed.",
                        "tool": "run_command",
                        "args": {"command": 'python -c "print(\'OK\')"'}
                    }
                else:
                    return {"tool": "finish", "args": {"summary": f"Failed to get diagnostic context. Obs: {last_obs[:100]}"}}
            else:
                return {"tool": "finish", "args": {"summary": "Finished successfully"}}

        elif self.scenario == "repeated_failure":
            return {
                "thought": "I keep doing the same wrong thing.",
                "tool": "run_command",
                "args": {"command": 'python -c "raise TypeError(\'Same error\')"'}
            }

        elif self.scenario == "max_attempts":
            # Return different errors so it doesn't trigger repeated failure detection
            err = f"Error {self.call_count}"
            return {
                "thought": f"Attempt {self.call_count}",
                "tool": "run_command",
                "args": {"command": f'python -c "raise Exception(\'{err}\')"'}
            }

        return {"tool": "finish", "args": {"summary": "Unknown scenario"}}


class TestAgentSelfDebugging(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_fail_then_succeed(self):
        client = DebugLLMClient("fail_then_succeed")
        agent = MiniSWEAgent(self.test_dir, llm_client=client, max_debug_attempts=2, verbose=False)
        result = agent.solve("Fix it")

        self.assertTrue(result.success)
        self.assertEqual(result.summary, "Finished successfully")
        self.assertEqual(client.call_count, 3)

    def test_repeated_failure_aborts(self):
        client = DebugLLMClient("repeated_failure")
        agent = MiniSWEAgent(self.test_dir, llm_client=client, max_debug_attempts=5, verbose=False)
        result = agent.solve("Fix it")

        self.assertFalse(result.success)
        self.assertIn("repeated identical failure", result.summary)
        # Call 1: fails (attempt 1) -> Call 2: repeats same failure -> Aborts immediately
        self.assertEqual(client.call_count, 2)

    def test_max_attempts_reached(self):
        client = DebugLLMClient("max_attempts")
        agent = MiniSWEAgent(self.test_dir, llm_client=client, max_debug_attempts=2, verbose=False)
        result = agent.solve("Fix it")

        self.assertFalse(result.success)
        self.assertIn("Failed after 2 debug attempts", result.summary)
        # Call 1: fails (attempt 1) -> Call 2: fails (attempt 2) -> Call 3: fails (attempt 3) -> Aborts
        self.assertEqual(client.call_count, 3)

if __name__ == "__main__":
    unittest.main()
