"""Integration tests for MiniSWEAgent solving real bugs in the sandbox."""

import os
import unittest
from pathlib import Path
from mini_swe_agent.agent import MiniSWEAgent
from mini_swe_agent.llm import DeterministicSWEClient


def reset_sandbox(sandbox_dir: Path):
    """Reset the sandbox files to their initial buggy state."""
    pricing_file = sandbox_dir / "shop" / "pricing.py"
    cart_file = sandbox_dir / "shop" / "cart.py"

    pricing_content = '''"""Pricing utility functions."""

def calculate_discount(total: float, discount_percent: float) -> float:
    """
    Calculate the discounted total given a total amount and a percentage discount (0-100).
    
    BUG #1: Incorrect formula!
    Instead of multiplying by (discount_percent / 100.0), it directly multiplies by discount_percent.
    For example, 10% discount on 100 yields 100 * 10 = 1000 instead of 10.0 discount (final 90.0).
    """
    discount_amount = total * discount_percent  # <--- BUG HERE
    return round(total - discount_amount, 2)
'''
    with open(pricing_file, "w", encoding="utf-8") as f:
        f.write(pricing_content)

    cart_content = '''"""Shopping Cart implementation."""

from typing import Dict
from .pricing import calculate_discount


class ItemNotFoundError(Exception):
    """Raised when an item is not found in the cart."""
    pass


class ShoppingCart:
    """Manages items, quantities, and totals."""

    def __init__(self):
        self.items: Dict[str, float] = {}  # item_name -> price
        self.quantities: Dict[str, int] = {}  # item_name -> quantity

    def add_item(self, name: str, price: float, quantity: int = 1) -> None:
        if quantity <= 0:
            raise ValueError("Quantity must be positive.")
        if name in self.items:
            self.quantities[name] += quantity
        else:
            self.items[name] = price
            self.quantities[name] = quantity

    def remove_item(self, name: str) -> None:
        """
        Remove an item from the cart.
        
        BUG #2:
        If `name` is not in the cart, accessing self.items[name] raises raw KeyError.
        The specification and callers expect `ItemNotFoundError` to be raised!
        """
        # Buggy code:
        del self.items[name]  # <--- BUG HERE: raises KeyError if missing
        del self.quantities[name]

    def subtotal(self) -> float:
        total = 0.0
        for name, price in self.items.items():
            total += price * self.quantities[name]
        return round(total, 2)

    def total_with_discount(self, discount_percent: float) -> float:
        sub = self.subtotal()
        return calculate_discount(sub, discount_percent)
'''
    with open(cart_file, "w", encoding="utf-8") as f:
        f.write(cart_content)


class TestMiniSWEAgent(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.root_dir = Path(__file__).resolve().parent.parent
        cls.sandbox_dir = cls.root_dir / "sandbox" / "mini_shop"

    def setUp(self):
        reset_sandbox(self.sandbox_dir)

    def test_solve_bug_1_discount_calculation(self):
        """Test agent autonomously resolving Bug 1 (discount formula)."""
        issue = (
            "Issue #1: calculate_discount(100.0, 10.0) yields -900.0 instead of 90.00. "
            "The formula multiplies total by discount directly instead of percent / 100.0. "
            "Please fix shop/pricing.py and verify with tests."
        )

        agent = MiniSWEAgent(
            workspace_dir=str(self.sandbox_dir),
            llm_client=DeterministicSWEClient(),
            verbose=False,
        )

        result = agent.solve(issue)

        self.assertTrue(result.success, f"Agent failed to solve Issue #1: {result.summary}")
        self.assertIn("shop/pricing.py", result.summary)

        # Verify that tests in the sandbox now pass
        verify_output = agent.tools.run_command("python -m unittest tests/test_cart.py -k test_discount_calculation")
        self.assertIn("OK", verify_output)

    def test_solve_bug_2_remove_item_error(self):
        """Test agent autonomously resolving Bug 2 (KeyError on missing item)."""
        issue = (
            "Issue #2: cart.remove_item raises KeyError when item is not in cart. "
            "It should raise ItemNotFoundError as defined in shop/cart.py. "
            "Please fix shop/cart.py and verify with tests."
        )

        agent = MiniSWEAgent(
            workspace_dir=str(self.sandbox_dir),
            llm_client=DeterministicSWEClient(),
            verbose=False,
        )

        result = agent.solve(issue)

        self.assertTrue(result.success, f"Agent failed to solve Issue #2: {result.summary}")
        self.assertIn("shop/cart.py", result.summary)

        # Verify that tests in the sandbox now pass
        verify_output = agent.tools.run_command("python -m unittest tests/test_cart.py -k test_remove_missing_item_raises_item_not_found")
        self.assertIn("OK", verify_output)


if __name__ == "__main__":
    unittest.main()
