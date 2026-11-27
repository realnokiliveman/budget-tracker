"""Tests for saving/loading JSON and for currency conversion online and offline."""

import json
from datetime import date
from decimal import Decimal

import pytest

from budget.rates import CurrencyConverter
from budget.storage import JsonStorage, atomic_write
from budget.tracker import BudgetTracker

FAKE_REPLY = {"result": "success", "rates": {"USD": 1, "THB": 34, "EUR": 0.5}}


def offline():
    raise OSError("no internet")


def test_save_then_load_gives_the_same_budget(tmp_path):
    storage = JsonStorage(tmp_path / "budget.json")
    budget = BudgetTracker()
    budget.add_expense("42", "books", date(2026, 11, 1))
    storage.save(budget)
    assert storage.load().expenses == budget.expenses


def test_missing_file_gives_empty_budget(tmp_path):
    storage = JsonStorage(tmp_path / "nothing.json")
    assert storage.load().expenses == []
    assert storage.warning is None


def test_broken_file_is_backed_up_not_crashing(tmp_path):
    path = tmp_path / "budget.json"
    path.write_text("{not json", encoding="utf-8")
    storage = JsonStorage(path)
    assert storage.load().expenses == []
    assert storage.warning is not None
    assert (tmp_path / "budget.json.broken").exists()


def test_atomic_write_keeps_old_file_if_writing_fails(tmp_path):
    path = tmp_path / "budget.json"
    path.write_text("old", encoding="utf-8")
    with pytest.raises(RuntimeError), atomic_write(path) as file:
        file.write("half")
        raise RuntimeError("disk full")
    assert path.read_text(encoding="utf-8") == "old"
    assert list(tmp_path.iterdir()) == [path]


def test_converter_uses_api_and_saves_a_copy(tmp_path):
    cache = tmp_path / "rates.json"
    converter = CurrencyConverter(cache, fetcher=lambda: FAKE_REPLY)
    assert converter.convert(Decimal("340"), "THB", "EUR") == Decimal("5.00")
    assert json.loads(cache.read_text(encoding="utf-8")) == FAKE_REPLY
    assert converter.source.startswith("live")


def test_converter_works_offline_from_saved_copy(tmp_path):
    cache = tmp_path / "rates.json"
    cache.write_text(json.dumps(FAKE_REPLY), encoding="utf-8")
    converter = CurrencyConverter(cache, fetcher=offline)
    assert converter.convert(Decimal("1"), "USD", "THB") == Decimal("34.00")
    assert converter.source.startswith("offline")


def test_converter_falls_back_to_seed_on_fresh_clone(tmp_path):
    converter = CurrencyConverter(tmp_path / "none.json", fetcher=offline)
    assert converter.convert(Decimal("100"), "USD", "USD") == Decimal("100.00")
    assert converter.source.startswith("built-in")


def test_converter_rejects_unknown_currency(tmp_path):
    converter = CurrencyConverter(tmp_path / "r.json", fetcher=lambda: FAKE_REPLY)
    with pytest.raises(ValueError):
        converter.convert(Decimal("1"), "THB", "ABC")


def test_converter_with_nothing_available_raises(tmp_path):
    converter = CurrencyConverter(
        tmp_path / "a.json", seed_path=tmp_path / "b.json", fetcher=offline
    )
    with pytest.raises(ValueError):
        converter.load_rates()
