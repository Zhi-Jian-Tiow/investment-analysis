"""Price fetching, isolated behind a PriceProvider interface (architecture
§11.1) so yfinance — an unofficial, no-SLA scraper (R-001) — can be swapped
for a paid provider later without touching any calling code.
"""

import asyncio
from decimal import Decimal
from typing import Protocol


class PriceFetchError(Exception):
    """Raised for any failure to obtain a valid price: network/HTTP error,
    an empty/delisted response, or a non-positive price. Callers (the retry
    wrapper in service.py) treat every failure mode identically — there is
    no case where a caller needs to distinguish *why* a fetch failed.
    """


class PriceProvider(Protocol):
    async def fetch_price(self, stock_code: str) -> Decimal:
        """Returns the latest end-of-day close for `stock_code`. Raises
        PriceFetchError if no valid price could be obtained."""
        ...


# Bursa Malaysia's yfinance ticker suffix. Verified against a real fetch
# (1023.KL / CIMB) during development — yfinance has no documented API
# reference for this, only the convention itself.
_BURSA_SUFFIX = ".KL"


class YFinancePriceProvider:
    """Architecture §11.1: 30-second timeout (yfinance's own default),
    called only from this cron path, never from a request handler.
    """

    async def fetch_price(self, stock_code: str) -> Decimal:
        loop = asyncio.get_running_loop()
        try:
            price = await loop.run_in_executor(None, self._fetch_sync, stock_code)
        except PriceFetchError:
            raise
        except Exception as exc:  # yfinance can raise anything from requests/urllib on network failure
            raise PriceFetchError(f"{stock_code}: {exc}") from exc

        if price is None or price <= 0:
            # EC-016: never surface 0/negative as a valid price.
            raise PriceFetchError(f"{stock_code}: no valid price in response")
        return price

    def _fetch_sync(self, stock_code: str) -> Decimal | None:
        import yfinance as yf

        ticker = yf.Ticker(f"{stock_code}{_BURSA_SUFFIX}")
        # 5 days, not 1: skips cleanly over a single missing/holiday-adjacent
        # row in yfinance's own data without extra retry logic on our side.
        history = ticker.history(period="5d")
        if history.empty:
            return None
        last_close = history["Close"].iloc[-1]
        # str() first: yfinance/pandas floats carry FP noise (e.g.
        # 7.889999866485596 for what is actually 7.89) — going through str()
        # at Python's default float repr precision, then rounding to BR-026's
        # 4dp, avoids baking that noise into a Decimal.
        return Decimal(str(round(float(last_close), 4)))
