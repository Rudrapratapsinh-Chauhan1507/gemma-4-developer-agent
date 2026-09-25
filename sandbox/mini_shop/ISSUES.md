# Repository Issues Catalog

## Issue #1: `calculate_discount` calculates negative or inflated totals
**Description**:
When applying a percentage discount (e.g. 10%), `calculate_discount(100.0, 10.0)` produces `-900.0` instead of `90.00`.
The discount formula appears to treat the discount as a direct multiplier rather than a percentage (e.g. `10% = 0.10`).
Please inspect `shop/pricing.py` and fix the formula so that discounts from `0.0` to `100.0` percent are correctly calculated and subtracted from the total.

---

## Issue #2: `remove_item` raises unhandled `KeyError` when item not present
**Description**:
When attempting to remove an item that is not currently in the shopping cart (e.g., `cart.remove_item("Pen")`), the code raises a raw Python `KeyError`.
The library defines a custom exception `ItemNotFoundError` in `shop/cart.py`, but it is never raised.
Callers expect `cart.remove_item(item_name)` to raise `ItemNotFoundError` when the item does not exist in the cart.
Please inspect `shop/cart.py` and ensure `ItemNotFoundError` is raised when the item is missing.
