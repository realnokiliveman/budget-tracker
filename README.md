# Budget tracker

A small command-line program that tracks what you spend: spending by category,
a monthly limit for each category, and a monthly summary. You can also see a
month's total in another currency (live rates, with an offline copy so it works
without internet).

CS105BKK final project, by Lasha.

## Requirements

- Python 3.12 or newer
- Nothing else is needed to run it. `pytest` and `ruff` are only for development.

## Run it

### macOS

```bash
git clone https://github.com/realnokiliveman/budget-tracker.git
cd budget-tracker
python3 main.py          # or: python3 -m budget
```

### Windows (PowerShell or CMD)

```powershell
git clone https://github.com/realnokiliveman/budget-tracker.git
cd budget-tracker
py main.py               # or: python main.py, or: py -m budget
```

Your data is saved to `data/budget.json` when you quit (menu `0`, Ctrl+C or
Ctrl+D) and loaded again next time.

## What it does

```
=== Budget tracker ===
1  Add an expense
2  List expenses for a month
3  Set a category limit
4  Remove a category limit
5  Monthly summary
6  Month total in another currency
0  Save and quit
```

Example summary:

```
--- 2026-11 (THB) ---
food              1830.00   OVER by 330.00
transport          420.50   579.50 left of 1000.00
TOTAL             2250.50
```

## Run the tests and the linter

```bash
python -m pip install pytest ruff     # macOS: python3 -m pip ...
python -m pytest
python -m ruff check .
```

## How the code is organised

| File | Job |
| --- | --- |
| `budget/models.py` | `Expense` and `CategorySummary` dataclasses; checking amounts and category names |
| `budget/tracker.py` | `BudgetTracker`: stores expenses and limits, does the sums |
| `budget/storage.py` | `JsonStorage`: saves and loads with `pathlib`; `atomic_write` context manager |
| `budget/rates.py` | `CurrencyConverter`: public API, offline JSON copy |
| `budget/cli.py` | `BudgetApp`: the menu; `friendly_errors` decorator |
| `main.py`, `budget/__main__.py` | Entry points |

How it covers the course topics:

- **Classes:** `Expense`, `CategorySummary` (dataclasses, `@property`, `__str__`),
  `BudgetTracker`, `JsonStorage`, `CurrencyConverter`, `BudgetApp`. The app is
  built by composition: `BudgetApp` *has a* tracker, a storage and a converter.
- **Errors:** bad input is asked again; a missing file starts an empty budget; a
  broken file is moved to `budget.json.broken` and the program carries on.
- **Advanced Python:** a generator (`BudgetTracker.expenses_in_month`), a
  decorator (`friendly_errors`) and a context manager (`atomic_write`).
- **API bonus:** [open.er-api.com](https://open.er-api.com/v6/latest/USD), no key
  needed. Each good reply is saved to `data/rates_cache.json`. Offline, the
  program uses that copy, or `budget/rates_seed.json` on a fresh clone.

## Design choices

- **Money is `Decimal`, not `float`.** `0.1 + 0.2` is `0.30000000000000004` as a
  float. Amounts are stored as strings in JSON so they stay exact.
- **Safe saving.** The file is written to `budget.json.tmp` and then swapped in,
  so a crash while saving can't leave a half-written budget.
- **The tracker never prints or reads files.** Only `cli.py` talks to the user
  and only `storage.py` touches the disk, so the logic is easy to test.
