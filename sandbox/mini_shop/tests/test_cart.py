"""Unittest test suite for ShoppingCart and pricing."""

import unittest
from shop.cart import ShoppingCart, ItemNotFoundError
from shop.pricing import calculate_discount


class TestShoppingCart(unittest.TestCase):

    def test_add_item_and_subtotal(self):
        """Normal behavior: adding items and calculating subtotal."""
        cart = ShoppingCart()
        cart.add_item("Apple", 1.50, 2)
        cart.add_item("Banana", 0.50, 4)
        self.assertEqual(cart.subtotal(), 5.00)

    def test_discount_calculation(self):
        """Issue #1: Discount calculation percentage logic."""
        total = 100.0
        discount = 10.0  # 10%
        result = calculate_discount(total, discount)
        # Expected: 100 - (100 * 0.10) = 90.00
        self.assertEqual(result, 90.00, f"Expected 90.00, but got {result}")

    def test_remove_missing_item_raises_item_not_found(self):
        """Issue #2: Removing an item not in cart should raise ItemNotFoundError."""
        cart = ShoppingCart()
        cart.add_item("Book", 10.00, 1)
        with self.assertRaises(ItemNotFoundError):
            cart.remove_item("Pen")


if __name__ == "__main__":
    unittest.main()
