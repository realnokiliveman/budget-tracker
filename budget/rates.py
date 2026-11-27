"""Currency conversion with a free public API and an offline JSON copy.

API: https://open.er-api.com/v6/latest/USD (no key needed).
Every good reply is saved to ``data/rates_cache.json``. With no internet the
program uses that copy, and on a fresh clone with no copy yet it falls back to
``budget/rates_seed.json``, a real reply shipped with the code.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from budget.storage import atomic_write

API_URL = "https://open.er-api.com/v6/latest/USD"
SEED_PATH = Path(__file__).with_name("rates_seed.json")
TIMEOUT_SECONDS = 5


def fetch_from_api(url: str = API_URL) -> dict:
    """Download the latest USD rates. Raises OSError or ValueError on failure."""
    request = urllib.request.Request(url, headers={"User-Agent": "budget-tracker"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


class CurrencyConverter:
    """Converts money between currencies, online or offline."""

    def __init__(
        self,
        cache_path: Path,
        seed_path: Path = SEED_PATH,
        fetcher: Callable[[], dict] = fetch_from_api,
    ) -> None:
        self.cache_path = Path(cache_path)
        self.seed_path = Path(seed_path)
        self._fetcher = fetcher
        self._reply: dict | None = None
        self.source = "not loaded"

    @staticmethod
    def _is_valid(reply: object) -> bool:
        return (
            isinstance(reply, dict)
            and reply.get("result") == "success"
            and isinstance(reply.get("rates"), dict)
        )

    def _read_json(self, path: Path) -> dict | None:
        try:
            reply = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return reply if self._is_valid(reply) else None

    def load_rates(self) -> dict[str, Decimal]:
        """Get rates (per 1 USD): live API, else saved copy, else seed file."""
        try:
            reply = self._fetcher()
        except (OSError, ValueError, urllib.error.URLError):
            reply = None
        if self._is_valid(reply):
            self.source = "live from open.er-api.com"
            try:
                with atomic_write(self.cache_path) as file:
                    json.dump(reply, file, indent=2)
            except OSError:
                pass  # converting still works, we just can't save the copy
        elif (reply := self._read_json(self.cache_path)) is not None:
            self.source = "offline copy (data/rates_cache.json)"
        elif (reply := self._read_json(self.seed_path)) is not None:
            self.source = "built-in offline rates"
        else:
            raise ValueError("no exchange rates available, online or offline")
        self._reply = reply
        updated = reply.get("time_last_update_utc")
        if updated:
            self.source += f", updated {updated}"
        return {code: Decimal(str(rate)) for code, rate in reply["rates"].items()}

    def convert(self, amount: Decimal, from_code: str, to_code: str) -> Decimal:
        """Convert an amount, e.g. ``convert(Decimal("100"), "THB", "GEL")``."""
        rates = self.load_rates()
        from_code, to_code = from_code.strip().upper(), to_code.strip().upper()
        for code in (from_code, to_code):
            if code not in rates:
                raise ValueError(f"unknown currency code '{code}'")
        result = amount / rates[from_code] * rates[to_code]
        return result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
