"""The BudgetTracker: holds expenses and limits, and does the sums."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal

from budget.models import CategorySummary, Expense, clean_category, parse_amount

DEFAULT_CURRENCY = "THB"


class BudgetTracker:
    """Keeps a list of expenses and a limit per category.

    It knows nothing about files or the screen: storage and the CLI use it.
    """

    def __init__(
        self,
        currency: str = DEFAULT_CURRENCY,
        expenses: list[Expense] | None = None,
        limits: dict[str, Decimal] | None = None,
    ) -> None:
        self.currency = currency.upper()
        self._expenses: list[Expense] = list(expenses or [])
        self._limits: dict[str, Decimal] = dict(limits or {})

    @property
    def expenses(self) -> list[Expense]:
        """A copy of all expenses, oldest first."""
        return sorted(self._expenses, key=lambda expense: expense.day)

    @property
    def limits(self) -> dict[str, Decimal]:
        """A copy of the monthly limit for each category."""
        return dict(self._limits)

    @property
    def categories(self) -> list[str]:
        """Every category that has an expense or a limit, sorted."""
        names = {expense.category for expense in self._expenses} | set(self._limits)
        return sorted(names)

    def add_expense(
        self,
        amount: str | Decimal,
        category: str,
        day: date | None = None,
        note: str = "",
    ) -> Expense:
        """Validate and store a new expense, and return it."""
        expense = Expense(
            amount=parse_amount(amount),
            category=clean_category(category),
            day=day or date.today(),
            note=note.strip(),
        )
        self._expenses.append(expense)
        return expense

    def set_limit(self, category: str, amount: str | Decimal) -> None:
        """Set the monthly spending limit for a category."""
        self._limits[clean_category(category)] = parse_amount(amount)

    def remove_limit(self, category: str) -> None:
        """Remove a category's limit. Raises KeyError if it has none."""
        name = clean_category(category)
        if name not in self._limits:
            raise KeyError(f"'{name}' has no limit")
        del self._limits[name]

    def expenses_in_month(self, year: int, month: int) -> Iterator[Expense]:
        """Yield the expenses of one month, oldest first (a generator)."""
        for expense in self.expenses:
            if expense.day.year == year and expense.day.month == month:
                yield expense

    def total_for_month(self, year: int, month: int) -> Decimal:
        """Total spending in one month."""
        return sum(
            (expense.amount for expense in self.expenses_in_month(year, month)),
            Decimal("0.00"),
        )

    def monthly_summary(self, year: int, month: int) -> list[CategorySummary]:
        """Spending per category in one month, with limits, biggest first."""
        spent: dict[str, Decimal] = dict.fromkeys(self._limits, Decimal("0.00"))
        for expense in self.expenses_in_month(year, month):
            spent[expense.category] = (
                spent.get(expense.category, Decimal("0.00")) + expense.amount
            )
        summaries = [
            CategorySummary(name, total, self._limits.get(name))
            for name, total in spent.items()
        ]
        return sorted(summaries, key=lambda item: (-item.spent, item.category))

    def to_dict(self) -> dict:
        """Everything as JSON-friendly data."""
        return {
            "currency": self.currency,
            "limits": {name: str(value) for name, value in self._limits.items()},
            "expenses": [expense.to_dict() for expense in self.expenses],
        }

    @classmethod
    def from_dict(cls, data: dict) -> BudgetTracker:
        """Rebuild a tracker from JSON data. Raises ValueError if it is broken."""
        if not isinstance(data, dict):
            raise ValueError("the budget file should hold a JSON object")
        try:
            limits = {
                clean_category(name): parse_amount(value)
                for name, value in data.get("limits", {}).items()
            }
            expenses = [Expense.from_dict(item) for item in data.get("expenses", [])]
        except (AttributeError, TypeError) as error:
            raise ValueError("the budget file has the wrong shape") from error
        currency = str(data.get("currency", DEFAULT_CURRENCY))
        return cls(currency=currency, expenses=expenses, limits=limits)
