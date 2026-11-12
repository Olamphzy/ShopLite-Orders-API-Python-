from decimal import Decimal, ROUND_HALF_UP


def to_cents(dollars: float) -> int:
    """Converts a dollar amount (as stored in the products table) to whole cents."""
    return int((Decimal(str(dollars)) * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
