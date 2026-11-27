"""The text menu: asks questions, calls the tracker, prints answers."""

from __future__ import annotations

import functools
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import TypeVar

from budget.models import clean_category, parse_amount
from budget.rates import CurrencyConverter
from budget.storage import JsonStorage
from budget.tracker import BudgetTracker

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MAX_TRIES = 3
MONTH_PROMPT = "Month YYYY-MM (blank = this month): "
T = TypeVar("T")

MENU = """
=== Budget tracker ===
1  Add an expense
2  List expenses for a month
3  Set a category limit
4  Remove a category limit
5  Monthly summary
6  Month total in another currency
0  Save and quit
"""


def friendly_errors(command: Callable) -> Callable:
    """Decorator: turn bad input into a short message instead of a traceback."""

    @functools.wraps(command)
    def wrapper(self: BudgetApp, *args, **kwargs):
        try:
            return command(self, *args, **kwargs)
        except (ValueError, KeyError) as error:
            message = error.args[0] if error.args else error
            self.say(f"! {message}")
        except OSError as error:
            self.say(f"! File problem: {error}")
        return None

    return wrapper


def parse_month(text: str, today: date | None = None) -> tuple[int, int]:
    """Read ``YYYY-MM`` (blank means this month). Raises ValueError."""
    text = text.strip()
    if not text:
        today = today or date.today()
        return today.year, today.month
    try:
        year_text, month_text = text.split("-")
        year, month = int(year_text), int(month_text)
    except ValueError:
        raise ValueError("write the month as YYYY-MM, e.g. 2026-11") from None
    if not 1 <= month <= 12 or not 1900 <= year <= 9999:
        raise ValueError("that month doesn't exist")
    return year, month


def parse_day(text: str) -> date:
    """Read ``YYYY-MM-DD`` (blank means today). Raises ValueError."""
    text = text.strip()
    if not text:
        return date.today()
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise ValueError("write the date as YYYY-MM-DD, e.g. 2026-11-27") from None


class BudgetApp:
    """Runs the menu loop. Input and output are swappable, so tests can drive it."""

    def __init__(
        self,
        storage: JsonStorage,
        converter: CurrencyConverter,
        ask: Callable[[str], str] = input,
        say: Callable[[str], None] = print,
    ) -> None:
        self.storage = storage
        self.converter = converter
        self.ask = ask
        self.say = say
        self.tracker: BudgetTracker = storage.load()
        if storage.warning:
            self.say(f"! {storage.warning} Starting with an empty budget.")

    def ask_valid(self, prompt: str, parse: Callable[[str], T]) -> T:
        """Ask until ``parse`` accepts the answer, so errors show up right away.

        Gives up with ValueError after MAX_TRIES wrong answers.
        """
        for _ in range(MAX_TRIES):
            answer = self.ask(prompt)
            try:
                return parse(answer)
            except ValueError as error:
                self.say(f"! {error} - try again.")
        raise ValueError("too many wrong answers, back to the menu")

    def run(self) -> None:
        """Show the menu until the user quits (or presses Ctrl+C / Ctrl+D)."""
        commands = {
            "1": self.add_expense,
            "2": self.list_expenses,
            "3": self.set_limit,
            "4": self.remove_limit,
            "5": self.show_summary,
            "6": self.convert_total,
        }
        try:
            while True:
                self.say(MENU)
                choice = self.ask("Choose: ").strip()
                if choice == "0":
                    break
                command = commands.get(choice)
                if command is None:
                    self.say("! Pick a number from the menu.")
                else:
                    command()
        except (KeyboardInterrupt, EOFError):
            self.say("")
        self.save()
        self.say("Bye!")

    @friendly_errors
    def save(self) -> None:
        """Write the budget to disk."""
        self.storage.save(self.tracker)
        self.say(f"Saved to {self.storage.path}")

    @friendly_errors
    def add_expense(self) -> None:
        """Ask for an expense and store it; warn if a limit is passed."""
        amount = self.ask_valid(f"Amount ({self.tracker.currency}): ", parse_amount)
        category = self.ask_valid("Category (e.g. food, transport): ", clean_category)
        day = self.ask_valid("Date YYYY-MM-DD (blank = today): ", parse_day)
        note = self.ask("Note (optional): ")
        expense = self.tracker.add_expense(amount, category, day, note)
        self.say(f"Added: {expense}")
        for summary in self.tracker.monthly_summary(day.year, day.month):
            if summary.category == expense.category and summary.is_over:
                self.say(f"! Careful, {summary}")

    @friendly_errors
    def list_expenses(self) -> None:
        """Print every expense in a month."""
        year, month = self.ask_valid(MONTH_PROMPT, parse_month)
        found = False
        for expense in self.tracker.expenses_in_month(year, month):
            self.say(str(expense))
            found = True
        if not found:
            self.say(f"No expenses in {year}-{month:02d}.")

    @friendly_errors
    def set_limit(self) -> None:
        """Set a monthly limit for a category."""
        category = self.ask_valid("Category: ", clean_category)
        amount = self.ask_valid(
            f"Monthly limit ({self.tracker.currency}): ", parse_amount
        )
        self.tracker.set_limit(category, amount)
        self.say("Limit saved.")

    @friendly_errors
    def remove_limit(self) -> None:
        """Remove a category's monthly limit."""
        self.tracker.remove_limit(self.ask("Category: "))
        self.say("Limit removed.")

    @friendly_errors
    def show_summary(self) -> None:
        """Print spending per category against limits, and the total."""
        year, month = self.ask_valid(MONTH_PROMPT, parse_month)
        summaries = self.tracker.monthly_summary(year, month)
        if not summaries:
            self.say(f"Nothing recorded for {year}-{month:02d}.")
            return
        self.say(f"\n--- {year}-{month:02d} ({self.tracker.currency}) ---")
        for summary in summaries:
            self.say(str(summary))
        total = self.tracker.total_for_month(year, month)
        self.say(f"{'TOTAL':<14}{total:>10}")

    @friendly_errors
    def convert_total(self) -> None:
        """Show a month's total in another currency."""
        year, month = self.ask_valid(MONTH_PROMPT, parse_month)
        target = self.ask("Convert to (e.g. USD, EUR, GEL): ")
        total = self.tracker.total_for_month(year, month)
        converted = self.converter.convert(total, self.tracker.currency, target)
        self.say(
            f"{total} {self.tracker.currency} = {converted} {target.strip().upper()}"
        )
        self.say(f"(rates: {self.converter.source})")


def main(data_dir: Path = DATA_DIR) -> None:
    """Build the app with real files and run it."""
    storage = JsonStorage(data_dir / "budget.json")
    converter = CurrencyConverter(cache_path=data_dir / "rates_cache.json")
    BudgetApp(storage, converter).run()
