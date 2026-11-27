"""Drive the menu with scripted answers, like a user would."""

from datetime import date

import pytest

from budget.cli import BudgetApp, parse_month
from budget.rates import CurrencyConverter
from budget.storage import JsonStorage


def make_app(tmp_path, answers):
    """Build an app whose input comes from a list and whose output is captured."""
    output: list[str] = []
    replies = iter(answers)

    def ask(prompt: str) -> str:
        try:
            return next(replies)
        except StopIteration:
            raise EOFError from None  # like pressing Ctrl+D

    app = BudgetApp(
        JsonStorage(tmp_path / "budget.json"),
        CurrencyConverter(tmp_path / "rates.json", fetcher=lambda: {}),
        ask=ask,
        say=output.append,
    )
    return app, output


def test_add_expense_and_quit_saves_to_disk(tmp_path):
    app, _ = make_app(tmp_path, ["1", "250", "food", "2026-11-27", "lunch", "0"])
    app.run()
    loaded = JsonStorage(tmp_path / "budget.json").load()
    assert [str(e.amount) for e in loaded.expenses] == ["250.00"]


def test_bad_amount_is_asked_again_right_away(tmp_path):
    answers = ["1", "abc", "-5", "99", "food", "", "", "0"]
    app, output = make_app(tmp_path, answers)
    app.run()
    assert sum("try again" in line for line in output) == 2
    assert len(app.tracker.expenses) == 1


def test_three_wrong_answers_go_back_to_menu_without_crash(tmp_path):
    app, output = make_app(tmp_path, ["1", "x", "y", "z", "0"])
    app.run()
    assert any("too many wrong answers" in line for line in output)
    assert app.tracker.expenses == []


def test_ctrl_d_still_saves(tmp_path):
    app, output = make_app(tmp_path, ["3", "food", "500"])  # then input runs out
    app.run()
    assert JsonStorage(tmp_path / "budget.json").load().limits == {"food": 500}
    assert output[-1] == "Bye!"


@pytest.mark.parametrize("bad", ["2026-13", "november", "2026/11", "26-11-2026"])
def test_parse_month_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        parse_month(bad)


def test_parse_month_blank_means_this_month():
    assert parse_month("", today=date(2026, 11, 27)) == (2026, 11)
