"""LLM clients and reasoning engines for Mini SWE Agent.

Includes:
1. BaseLLMClient: Abstract interface
2. DeterministicSWEClient: Phase-based state machine solver demonstrating the ideal ReAct loop
3. OllamaClient: Connects to local Ollama runtime (e.g. llama3.2:3b)
4. GeminiClient: Connects to Google Gemini API when GEMINI_API_KEY is configured
"""

import json
import os
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class BaseLLMClient(ABC):
    """Abstract interface for model reasoning."""

    @abstractmethod
    def generate_action(self, messages: List[Dict[str, str]], system_prompt: str) -> Dict[str, Any]:
        """Generate the next thought and tool action given conversation history."""
        pass


class DeterministicSWEClient(BaseLLMClient):
    """
    A phase-driven reasoning engine that demonstrates the ideal autonomous SWE trajectory:
    1. Reproduce: Run test suite to witness the failure & traceback
    2. Inspect: Read the implicated source file and lines
    3. Modify: Apply targeted edit to resolve the root cause
    4. Verify: Re-run tests to confirm exit code 0
    5. Conclude: Call finish with patch summary
    """

    def __init__(self):
        self.step_count = 0

    def _extract_last_action_and_observation(self, messages: List[Dict[str, str]]):
        """Extract the last tool executed and its observation from message history."""
        last_tool = None
        last_obs = ""
        for m in reversed(messages):
            if m["role"] == "user" and m["content"].startswith("Observation:"):
                last_obs = m["content"]
            elif m["role"] == "assistant" and "Action:" in m["content"]:
                match = re.search(r"Action:\s*(\w+)", m["content"])
                if match:
                    last_tool = match.group(1)
                    break
        return last_tool, last_obs

    def generate_action(self, messages: List[Dict[str, str]], system_prompt: str) -> Dict[str, Any]:
        user_issue = messages[0]["content"] if messages else ""
        last_tool, last_obs = self._extract_last_action_and_observation(messages)

        # Route to appropriate bug trajectory
        if "discount" in user_issue.lower() or "pricing" in user_issue.lower():
            return self._solve_discount(last_tool, last_obs)
        elif "remove_item" in user_issue.lower() or "keyerror" in user_issue.lower() or "cart" in user_issue.lower():
            return self._solve_remove_item(last_tool, last_obs)
        else:
            return {
                "thought": "I will explore the workspace files to identify the repository structure.",
                "tool": "list_files",
                "args": {"directory": "."}
            }

    def _solve_discount(self, last_tool: Optional[str], last_obs: str) -> Dict[str, Any]:
        # Step 1: Reproduce
        if last_tool is None:
            return {
                "thought": "First, I will run the existing test suite to reproduce the discount calculation failure.",
                "tool": "run_command",
                "args": {"command": "python -m unittest tests/test_cart.py -k test_discount_calculation"}
            }

        # Step 2: Inspect code after test failure
        if last_tool == "run_command" and ("FAIL" in last_obs or "Exit Code: 1" in last_obs):
            return {
                "thought": "The test failed with AssertionError. I will read shop/pricing.py to inspect the formula.",
                "tool": "read_file",
                "args": {"path": "shop/pricing.py", "start_line": 1, "end_line": 20}
            }

        # Step 3: Edit code after reading
        if last_tool == "read_file":
            return {
                "thought": "In shop/pricing.py, the calculation is total * discount_percent instead of total * (discount_percent / 100.0). I will edit the file to fix this.",
                "tool": "edit_file",
                "args": {
                    "path": "shop/pricing.py",
                    "target_string": "    discount_amount = total * discount_percent  # <--- BUG HERE\n    return round(total - discount_amount, 2)",
                    "replacement_string": "    discount_amount = total * (discount_percent / 100.0)\n    return round(total - discount_amount, 2)"
                }
            }

        # Step 4: Verify with tests after editing
        if last_tool == "edit_file":
            return {
                "thought": "The file was edited. I will re-run the tests to verify the fix.",
                "tool": "run_command",
                "args": {"command": "python -m unittest tests/test_cart.py -k test_discount_calculation"}
            }

        # Step 5: Conclude when tests pass
        if last_tool == "run_command" and ("OK" in last_obs or "Exit Code: 0" in last_obs):
            return {
                "thought": "The discount calculation tests now pass. The issue is resolved.",
                "tool": "finish",
                "args": {"summary": "Fixed discount calculation formula in shop/pricing.py by dividing percentage by 100.0."}
            }

        # Fallback
        return {
            "thought": "Checking final test status.",
            "tool": "run_command",
            "args": {"command": "python -m unittest discover -s tests"}
        }

    def _solve_remove_item(self, last_tool: Optional[str], last_obs: str) -> Dict[str, Any]:
        # Step 1: Reproduce
        if last_tool is None:
            return {
                "thought": "I will run the unit tests to reproduce the error when removing an item not in cart.",
                "tool": "run_command",
                "args": {"command": "python -m unittest tests/test_cart.py -k test_remove_missing_item_raises_item_not_found"}
            }

        # Step 2: Inspect code after test failure
        if last_tool == "run_command" and ("KeyError" in last_obs or "Exit Code: 1" in last_obs):
            return {
                "thought": "Test fails with raw KeyError. I will read shop/cart.py around remove_item to see how items are deleted.",
                "tool": "read_file",
                "args": {"path": "shop/cart.py", "start_line": 25, "end_line": 45}
            }

        # Step 3: Edit code after reading
        if last_tool == "read_file":
            return {
                "thought": "shop/cart.py deletes directly without checking if name is present. I will edit remove_item to raise ItemNotFoundError.",
                "tool": "edit_file",
                "args": {
                    "path": "shop/cart.py",
                    "target_string": "        # Buggy code:\n        del self.items[name]  # <--- BUG HERE: raises KeyError if missing\n        del self.quantities[name]",
                    "replacement_string": "        if name not in self.items:\n            raise ItemNotFoundError(f\"Item '{name}' not found in cart.\")\n        del self.items[name]\n        del self.quantities[name]"
                }
            }

        # Step 4: Verify with tests after editing
        if last_tool == "edit_file":
            return {
                "thought": "The fix was applied. Now I re-run unittest to check if ItemNotFoundError is raised properly.",
                "tool": "run_command",
                "args": {"command": "python -m unittest tests/test_cart.py -k test_remove_missing_item_raises_item_not_found"}
            }

        # Step 5: Conclude when tests pass
        if last_tool == "run_command" and ("OK" in last_obs or "Exit Code: 0" in last_obs):
            return {
                "thought": "The test passes and ItemNotFoundError is correctly raised. Issue is resolved.",
                "tool": "finish",
                "args": {"summary": "Updated ShoppingCart.remove_item in shop/cart.py to raise ItemNotFoundError when key is absent."}
            }

        # Fallback
        return {
            "thought": "Checking test status.",
            "tool": "run_command",
            "args": {"command": "python -m unittest discover -s tests"}
        }


class OllamaClient(BaseLLMClient):
    """Client for local Ollama server (e.g. http://localhost:11434)."""

    def __init__(self, model_name: str = "llama3.2:3b", base_url: str = "http://127.0.0.1:11434"):
        self.model_name = model_name
        self.base_url = base_url

    def generate_action(self, messages: List[Dict[str, str]], system_prompt: str) -> Dict[str, Any]:
        import urllib.request

        payload = {
            "model": self.model_name,
            "messages": [{"role": "system", "content": system_prompt}] + messages,
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.1}
        }

        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data.get("message", {}).get("content", "{}")
            return json.loads(content)


class GeminiClient(BaseLLMClient):
    """Client for Google Gemini API."""

    def __init__(self, model_name: str = "gemini-2.5-flash", api_key: Optional[str] = None):
        from google import genai
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment.")
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = model_name

    def generate_action(self, messages: List[Dict[str, str]], system_prompt: str) -> Dict[str, Any]:
        prompt_text = f"System:\n{system_prompt}\n\nConversation:\n"
        for m in messages:
            prompt_text += f"{m['role']}: {m['content']}\n"
        prompt_text += "\nRespond strictly with JSON object containing 'thought', 'tool', and 'args'."

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt_text,
        )
        text = response.text or "{}"
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(text)
