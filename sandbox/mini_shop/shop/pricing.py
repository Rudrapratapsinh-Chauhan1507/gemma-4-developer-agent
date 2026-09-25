"""Pricing utility functions."""

def calculate_discount(total: float, discount_percent: float) -> float:
    """
    Calculate the discounted total given a total amount and a percentage discount (0-100).
    
    BUG #1: Incorrect formula!
    Instead of multiplying by (discount_percent / 100.0), it directly multiplies by discount_percent.
    For example, 10% discount on 100 yields 100 * 10 = 1000 instead of 10.0 discount (final 90.0).
    """
    discount_amount = total * discount_percent  # <--- BUG HERE
    return round(total - discount_amount, 2)
