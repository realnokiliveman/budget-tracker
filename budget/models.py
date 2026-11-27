"""Small data classes: one expense, and the summary of one category."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENT = Decimal("0.01")
MAX_AMOUNT = Decimal("1000000000")
MAX_CATEGORY_LENGTH = 30


def parse_amount(text: str | int | float | Decimal) -> Decimal:
    """Turn user input like ``"12.5"`` or ``"12,5"`` into a money Decimal.

    Raises ValueError for text that is not a number, for zero or negative
    amounts, and for absurdly large ones.
    """
    try:
        value = Decimal(str(text).strip().replace(",", "."))
    except InvalidOperation:
        raise ValueError(f"'{text}' is not a number") from None
    if not value.is_finite() or value <= 0:
        raise ValueError("the amount must be a positive number")
    if value > MAX_AMOUNT:
        raise ValueError("that amount is too large")
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def clean_category(name: str) -> str:
    """Normalise a category name: trimmed, lower case, not empty."""
    cleaned = " ".join(str(name).split()).lower()
    if not cleaned:
        raise ValueError("the category can't be empty")
    if len(cleaned) > MAX_CATEGORY_LENGTH:
        raise ValueError(f"keep the category under {MAX_CATEGORY_LENGTH} characters")
    return cleaned


@dataclass(frozen=True)
class Expense:
    """One thing you spent money on."""

    amount: Decimal
    category: str
    day: date
    note: str = ""

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-friendly dict (money stays a string, so it stays exact)."""
        return {
            "amount": str(self.amount),
            "category": self.category,
            "day": self.day.isoformat(),
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Expense:
        """Build an Expense from a dict loaded from JSON. Raises ValueError."""
        try:
            return cls(
                amount=parse_amount(data["amount"]),
                category=clean_category(data["category"]),
                day=date.fromisoformat(data["day"]),
                note=str(data.get("note", "")),
            )
        except (KeyError, TypeError) as error:
            raise ValueError(f"broken expense record: {data!r}") from error

    def __str__(self) -> str:
        note = f"  {self.note}" if self.note else ""
        return f"{self.day.isoformat()}  {self.category:<14}{self.amount:>10}{note}"


@dataclass(frozen=True)
class CategorySummary:
    """How much was spent in one category in one month, against its limit."""

    category: str
    spent: Decimal
    limit: Decimal | None = None

    @property
    def remaining(self) -> Decimal | None:
        """Money left before the limit, or None if there is no limit."""
        if self.limit is None:
            return None
        return self.limit - self.spent

    @property
    def is_over(self) -> bool:
        """True when spending went past the limit."""
        return self.limit is not None and self.spent > self.limit

    def __str__(self) -> str:
        if self.limit is None:
            status = "no limit"
        elif self.is_over:
            status = f"OVER by {-self.remaining}"
        else:
            status = f"{self.remaining} left of {self.limit}"
        return f"{self.category:<14}{self.spent:>10}   {status}"
