"""
FX conversion service.
Source: frankfurter.app — free, no API key required.
Rates are fetched once per day and cached in the database.

Note: frankfurter.app uses ECB data and does not support CNH (offshore RMB).
We proxy CNH through CNY, which trades nearly at parity with CNH.
"""
from datetime import date, timedelta
from decimal import Decimal
import logging
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models.fx_rate import FxRate

logger = logging.getLogger(__name__)

FRANKFURTER_BASE = "https://api.frankfurter.dev/v1"

# Currencies we need to convert to HKD
# CNH is not supported by frankfurter.app — proxied through CNY
TRACKED_CURRENCIES = ["USD", "GBP", "EUR", "AUD", "CNY", "SGD", "JPY"]

# Emergency fallbacks when API and DB both unavailable (approximate mid-rates)
EMERGENCY_RATES: dict[str, Decimal] = {
    "USD": Decimal("7.78"),
    "GBP": Decimal("9.85"),
    "AUD": Decimal("5.00"),
    "EUR": Decimal("8.50"),
    "SGD": Decimal("5.80"),
    "JPY": Decimal("0.052"),   # ~1 JPY = 0.052 HKD
    "CNY": Decimal("1.07"),
    "CNH": Decimal("1.07"),    # CNH ≈ CNY
}


async def get_rate(
    session: AsyncSession,
    from_currency: str,
    rate_date: date | None = None,
) -> Decimal:
    """
    Get the exchange rate from_currency → HKD for a given date.
    Returns 1.0 if from_currency is already HKD.
    Falls back to most recent available rate if date not found.

    CNH (offshore RMB) is proxied through CNY since frankfurter.app does not
    support CNH; the two currencies trade at near parity.
    """
    ccy = from_currency.upper()
    if ccy in ("HKD",):
        return Decimal("1.0")

    # Proxy CNH through CNY
    lookup_ccy = "CNY" if ccy == "CNH" else ccy

    target_date = rate_date or date.today()

    # Try DB cache first (check both the original ccy and lookup_ccy)
    row = await session.scalar(
        select(FxRate).where(
            FxRate.from_currency == lookup_ccy,
            FxRate.to_currency == "HKD",
            FxRate.rate_date == target_date,
        )
    )
    if row:
        return row.rate

    # Fetch from frankfurter.app
    rate = await _fetch_and_store(session, lookup_ccy, target_date)
    return rate


async def _fetch_and_store(
    session: AsyncSession,
    from_currency: str,
    target_date: date,
) -> Decimal:
    """Fetch rate from frankfurter.app and persist to DB.

    from_currency must be a currency supported by frankfurter.app (CNH already
    proxied to CNY by the caller).
    """
    date_str = target_date.isoformat()
    url = f"{FRANKFURTER_BASE}/{date_str}?from={from_currency}&to=HKD"

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            rate_value = Decimal(str(data["rates"]["HKD"]))
            actual_date = date.fromisoformat(data["date"])  # frankfurter returns closest trading day
            logger.info("FX fetched: %s/HKD = %s for %s", from_currency, rate_value, actual_date)
        except Exception as exc:
            logger.warning("FX fetch failed for %s on %s: %s", from_currency, date_str, exc)
            # Fallback: use most recent stored rate
            fallback = await session.scalar(
                select(FxRate)
                .where(FxRate.from_currency == from_currency, FxRate.to_currency == "HKD")
                .order_by(FxRate.rate_date.desc())
            )
            if fallback:
                logger.info("FX using cached rate for %s: %s", from_currency, fallback.rate)
                return fallback.rate
            # Hard-coded emergency fallbacks (approximate)
            emergency = EMERGENCY_RATES.get(from_currency, Decimal("1.0"))
            logger.warning("FX using emergency fallback for %s: %s", from_currency, emergency)
            return emergency

    # Upsert into DB
    existing = await session.scalar(
        select(FxRate).where(
            FxRate.from_currency == from_currency,
            FxRate.to_currency == "HKD",
            FxRate.rate_date == actual_date,
        )
    )
    if not existing:
        session.add(FxRate(
            rate_date=actual_date,
            from_currency=from_currency,
            to_currency="HKD",
            rate=rate_value,
        ))
        await session.commit()

    return rate_value


async def convert_to_hkd(
    session: AsyncSession,
    amount: Decimal,
    from_currency: str,
    rate_date: date | None = None,
) -> tuple[Decimal, Decimal]:
    """
    Convert an amount to HKD.
    Returns (hkd_amount, fx_rate_used).
    """
    rate = await get_rate(session, from_currency, rate_date)
    return amount * rate, rate


async def refresh_rates(session: AsyncSession, target_date: date | None = None) -> dict[str, Decimal]:
    """Fetch and store rates for all tracked currencies for a given date.
    CNH is also returned, proxied through the CNY rate.
    """
    target = target_date or date.today()
    rates: dict[str, Decimal] = {}
    for ccy in TRACKED_CURRENCIES:
        rates[ccy] = await _fetch_and_store(session, ccy, target)
    # Alias CNH = CNY
    rates["CNH"] = rates.get("CNY", EMERGENCY_RATES["CNH"])
    return rates
