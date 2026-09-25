"""Core ReAct Agent implementation for Mini SWE Agent."""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from .tools import ToolRegistry
from .prompt import SYSTEM_PROMPT
from .llm import BaseLLMClient, DeterministicSWEClient


@dataclass
class AgentStep:
    step_number: int
    thought: str
    tool: str
    args: Dict[str, Any]
    observation: str


@dataclass
class AgentResult:
    success: bool
    summary: str
    patch: str
    total_steps: int
    steps: List[AgentStep] = field(default_factory=list)


class MiniSWEAgent:
    """
    Autonomous ReAct Software Engineering Agent.
    
    Executes the loop:
    1. Plan / Reason over current issue & previous observations
    2. Act by selecting a tool and arguments
    3. Observe real environment feedback (file contents, test outputs, errors)
    4. Reflect and retry until passing tests confirm the resolution
    """

    def __init__(
        self,
        workspace_dir: str,
        llm_client: Optional[BaseLLMClient] = None,
        system_prompt: str = SYSTEM_PROMPT,
        max_steps: int = 10,
        verbose: bool = True,
    ):
        self.workspace_dir = workspace_dir
        self.tools = ToolRegistry(workspace_dir)
        self.llm = llm_client or DeterministicSWEClient()
        self.system_prompt = system_prompt
        self.max_steps = max_steps
        self.verbose = verbose

    def log(self, message: str) -> None:
        if self.verbose:
            try:
                print(message)
            except UnicodeEncodeError:
                # Graceful ASCII fallback for environments with restricted encoding
                print(message.encode("ascii", errors="replace").decode("ascii"))

    def solve(self, issue_description: str) -> AgentResult:
        """Run the autonomous loop to solve the specified issue."""
        self.log("\n" + "=" * 60)
        self.log("[START] SWE AGENT TASK")
        self.log(f"Issue: {issue_description.strip()}")
        self.log("=" * 60 + "\n")

        messages: List[Dict[str, str]] = [
            {"role": "user", "content": issue_description}
        ]
        steps_record: List[AgentStep] = []

        for step_idx in range(1, self.max_steps + 1):
            self.log(f"--- [Step {step_idx}/{self.max_steps}] ---")

            # 1. Reason & Plan next action
            try:
                action = self.llm.generate_action(messages, self.system_prompt)
            except Exception as e:
                self.log(f"[ERROR] LLM reasoning engine failed: {e}")
                break

            thought = action.get("thought", "No thought provided.")
            tool_name = action.get("tool", "")
            tool_args = action.get("args", {})

            self.log(f"[THOUGHT] {thought}")
            self.log(f"[ACTION]  {tool_name}({tool_args})")

            # 2. Check for completion
            if tool_name == "finish":
                summary = tool_args.get("summary", "Issue resolved.")
                patch = self.tools.get_patch()
                self.log("\n" + "=" * 60)
                self.log("[SUCCESS] AGENT FINISHED TASK")
                self.log(f"Summary: {summary}")
                if patch:
                    self.log(f"Generated Patch:\n{patch}")
                self.log("=" * 60 + "\n")
                return AgentResult(
                    success=True,
                    summary=summary,
                    patch=patch,
                    total_steps=step_idx,
                    steps=steps_record,
                )

            # 3. Execute tool action in workspace
            observation = self.tools.execute(tool_name, tool_args)
            self.log(f"[OBSERVATION]\n{observation}\n")

            # 4. Record step and update conversation history
            step_obj = AgentStep(
                step_number=step_idx,
                thought=thought,
                tool=tool_name,
                args=tool_args,
                observation=observation,
            )
            steps_record.append(step_obj)

            messages.append({
                "role": "assistant",
                "content": f"Action: {tool_name}\nArgs: {tool_args}\nThought: {thought}"
            })
            messages.append({
                "role": "user",
                "content": f"Observation:\n{observation}"
            })

        # If max steps exceeded
        self.log(f"[WARNING] Reached maximum step limit ({self.max_steps}) without finishing.")
        return AgentResult(
            success=False,
            summary="Max steps exceeded without resolution.",
            patch=self.tools.get_patch(),
            total_steps=self.max_steps,
            steps=steps_record,
        )
