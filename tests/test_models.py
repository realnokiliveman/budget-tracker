"""Tests for parsing money and categories, and for the small data classes."""

from datetime import date
from decimal import Decimal

import pytest

from budget.models import CategorySummary, Expense, clean_category, parse_amount


@pytest.mark.parametrize(
    ("text", "expected"),
    [("12.5", "12.50"), ("12,5", "12.50"), (" 7 ", "7.00"), ("0.005", "0.01")],
)
def test_parse_amount_accepts_normal_input(text, expected):
    assert parse_amount(text) == Decimal(expected)


@pytest.mark.parametrize("bad", ["", "abc", "0", "-5", "nan", "inf", "1e12"])
def test_parse_amount_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        parse_amount(bad)


def test_clean_category_normalises_spaces_and_case():
    assert clean_category("  Eating   OUT ") == "eating out"


@pytest.mark.parametrize("bad", ["", "   ", "x" * 31])
def test_clean_category_rejects_empty_and_too_long(bad):
    with pytest.raises(ValueError):
        clean_category(bad)


def test_expense_round_trips_through_dict():
    expense = Expense(Decimal("99.90"), "food", date(2026, 11, 27), "pad thai")
    assert Expense.from_dict(expense.to_dict()) == expense


def test_expense_from_broken_dict_raises_value_error():
    with pytest.raises(ValueError):
        Expense.from_dict({"amount": "10"})


def test_category_summary_over_and_under_limit():
    under = CategorySummary("food", Decimal("150"), Decimal("200"))
    over = CategorySummary("food", Decimal("250"), Decimal("200"))
    assert under.remaining == Decimal("50") and not under.is_over
    assert over.is_over and "OVER by 50" in str(over)


def test_category_summary_without_limit():
    summary = CategorySummary("fun", Decimal("10"))
    assert summary.remaining is None
    assert not summary.is_over
