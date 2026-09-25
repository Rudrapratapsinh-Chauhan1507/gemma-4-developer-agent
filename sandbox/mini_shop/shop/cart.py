"""Shopping Cart implementation."""

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
        if name not in self.items:
            raise ItemNotFoundError(f"Item '{name}' not found in cart.")
        del self.items[name]
        del self.quantities[name]

    def subtotal(self) -> float:
        total = 0.0
        for name, price in self.items.items():
            total += price * self.quantities[name]
        return round(total, 2)

    def total_with_discount(self, discount_percent: float) -> float:
        sub = self.subtotal()
        return calculate_discount(sub, discount_percent)
