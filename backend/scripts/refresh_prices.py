"""Thin cron entrypoint (architecture §13.2). Scheduled `30 9 * * 1-5`
(09:30 UTC / 5:30 PM MYT, Mon-Fri) as a Render cron job — that scheduling
itself is Epic 9 infrastructure (DEP-9.x), not something this script
configures. All actual logic lives in app.pricing.service.run_price_refresh,
which is unit-tested directly against a fake PriceProvider; this file only
wires up the DB session, the real yfinance provider, and the wall-clock
timeout.

Run manually with: uv run python scripts/refresh_prices.py
"""

import asyncio
import sys

# Every model module must be imported before any DB session is used — unlike
# app.main (which pulls these in transitively via its routers), this
# standalone script has nothing else that would import them, and
# PriceSnapshot.created_by_user_id's FK to `users` fails to resolve at
# flush time otherwise (same reasoning as tests/conftest.py's own explicit
# import block).
import app.admin.models  # noqa: F401
import app.auth.models  # noqa: F401
import app.portfolio.models  # noqa: F401
import app.pricing.models  # noqa: F401
from app.admin.service import release_price_refresh_lock
from app.database import AsyncSessionLocal
from app.monitoring import sentry_checkin
from app.pricing.provider import YFinancePriceProvider
from app.pricing.service import MONITOR_SLUG, run_price_refresh

_WALL_CLOCK_TIMEOUT_SECONDS = 60 * 60  # HIGH-R-004


async def main() -> int:
    provider = YFinancePriceProvider()
    async with AsyncSessionLocal() as db:
        try:
            result = await asyncio.wait_for(
                run_price_refresh(db, provider), timeout=_WALL_CLOCK_TIMEOUT_SECONDS
            )
        except TimeoutError:
            # run_price_refresh's own try/finally releases the lock during
            # cancellation unwind, but asyncio.wait_for's cancellation can
            # race that unwind — clear it again here defensively so a timeout
            # can never leave the lock held for its full 2-hour TTL.
            await release_price_refresh_lock(db)
            sentry_checkin(MONITOR_SLUG, "error", reason="wall_clock_timeout")
            print("refresh_prices: wall-clock timeout exceeded", file=sys.stderr)
            return 1

    if result.skipped_reason:
        print(f"refresh_prices: skipped ({result.skipped_reason})")
        return 0

    print(
        f"refresh_prices: fetched={len(result.fetched)} "
        f"rejected_deviation={len(result.rejected_deviation)} failed={len(result.failed)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
