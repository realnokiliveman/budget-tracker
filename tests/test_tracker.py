"""Tests for the BudgetTracker sums, limits and month filtering."""

from datetime import date
from decimal import Decimal

import pytest

from budget.tracker import BudgetTracker


@pytest.fixture
def tracker():
    budget = BudgetTracker()
    budget.add_expense("100", "food", date(2026, 11, 3))
    budget.add_expense("50.25", "Transport", date(2026, 11, 10))
    budget.add_expense("80", "food", date(2026, 11, 20))
    budget.add_expense("999", "food", date(2026, 10, 31))
    budget.set_limit("food", "150")
    return budget


def test_money_sums_are_exact():
    budget = BudgetTracker()
    for _ in range(3):
        budget.add_expense("0.1", "snacks", date(2026, 11, 1))
    assert budget.total_for_month(2026, 11) == Decimal("0.30")


def test_month_total_ignores_other_months(tracker):
    assert tracker.total_for_month(2026, 11) == Decimal("230.25")
    assert tracker.total_for_month(2026, 10) == Decimal("999.00")
    assert tracker.total_for_month(2026, 12) == Decimal("0.00")


def test_expenses_in_month_is_a_sorted_generator(tracker):
    result = tracker.expenses_in_month(2026, 11)
    assert iter(result) is result  # a generator, not a list
    assert [e.day.day for e in result] == [3, 10, 20]


def test_monthly_summary_flags_categories_over_limit(tracker):
    summary = {s.category: s for s in tracker.monthly_summary(2026, 11)}
    assert summary["food"].spent == Decimal("180.00")
    assert summary["food"].is_over
    assert not summary["transport"].is_over


def test_limit_shows_in_summary_even_with_no_spending():
    budget = BudgetTracker()
    budget.set_limit("rent", "9000")
    (only,) = budget.monthly_summary(2026, 11)
    assert only.category == "rent" and only.remaining == Decimal("9000.00")


def test_remove_missing_limit_raises_key_error(tracker):
    with pytest.raises(KeyError):
        tracker.remove_limit("holidays")


def test_bad_expense_is_not_stored(tracker):
    with pytest.raises(ValueError):
        tracker.add_expense("-20", "food")
    assert len(tracker.expenses) == 4


def test_tracker_round_trips_through_dict(tracker):
    copy = BudgetTracker.from_dict(tracker.to_dict())
    assert copy.expenses == tracker.expenses
    assert copy.limits == tracker.limits


@pytest.mark.parametrize("bad", [[], "text", {"expenses": [{"amount": "x"}]}])
def test_from_dict_rejects_broken_data(bad):
    with pytest.raises(ValueError):
        BudgetTracker.from_dict(bad)
