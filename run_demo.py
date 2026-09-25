"""Demonstration script for Mini SWE Agent solving real bugs in the sandbox."""

import sys
from pathlib import Path
from mini_swe_agent.agent import MiniSWEAgent
from mini_swe_agent.llm import DeterministicSWEClient
from tests.test_agent import reset_sandbox


def run():
    root_dir = Path(__file__).resolve().parent
    sandbox_dir = root_dir / "sandbox" / "mini_shop"

    print("=" * 70)
    print("      MINI SWE AGENT DEMONSTRATION (STAGE 1)")
    print("=" * 70)

    # -------------------------------------------------------------
    # DEMO 1: Bug #1 - Discount Calculation Formula
    # -------------------------------------------------------------
    print("\n>>> Setting up Demo 1: Bug #1 (Discount calculation logic)...")
    reset_sandbox(sandbox_dir)

    issue_1 = (
        "Issue #1: calculate_discount(100.0, 10.0) yields -900.0 instead of 90.00. "
        "The formula in shop/pricing.py multiplies total by discount directly instead of percent / 100.0. "
        "Please fix shop/pricing.py and verify with tests."
    )

    agent_1 = MiniSWEAgent(
        workspace_dir=str(sandbox_dir),
        llm_client=DeterministicSWEClient(),
        verbose=True,
    )
    result_1 = agent_1.solve(issue_1)

    print(f"\n[DEMO 1 RESULT] Success: {result_1.success} | Steps: {result_1.total_steps}")
    print(f"Summary: {result_1.summary}")

    # -------------------------------------------------------------
    # DEMO 2: Bug #2 - KeyError on Missing Item Removal
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    print(">>> Setting up Demo 2: Bug #2 (KeyError on missing item)...")
    reset_sandbox(sandbox_dir)

    issue_2 = (
        "Issue #2: cart.remove_item raises KeyError when item is not in cart. "
        "It should raise ItemNotFoundError as defined in shop/cart.py. "
        "Please fix shop/cart.py and verify with tests."
    )

    agent_2 = MiniSWEAgent(
        workspace_dir=str(sandbox_dir),
        llm_client=DeterministicSWEClient(),
        verbose=True,
    )
    result_2 = agent_2.solve(issue_2)

    print(f"\n[DEMO 2 RESULT] Success: {result_2.success} | Steps: {result_2.total_steps}")
    print(f"Summary: {result_2.summary}")

    print("\n" + "=" * 70)
    print("ALL DEMOS COMPLETED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    run()
