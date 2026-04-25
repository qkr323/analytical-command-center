"""
Portfolio history endpoints.

GET /history/snapshots          — monthly NAV snapshots (all accounts combined)
GET /history/changes            — month-over-month position changes
GET /history/snapshots/{date}   — full position breakdown on a specific date
"""
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict

from database import get_db
from models.position_snapshot import PositionSnapshot

router = APIRouter(prefix="/history", tags=["history"])


class BrokerValue(BaseModel):
    value_hkd: Decimal
    source: Literal["actual", "filled_forward"]
    as_of_date: date | None = None

    model_config = ConfigDict(json_encoders={Decimal: str})


class MonthlyNAV(BaseModel):
    snapshot_date: date
    total_nav_hkd: Decimal
    by_broker: dict[str, BrokerValue]
    by_asset_type: dict[str, Decimal]


class PositionChange(BaseModel):
    symbol: str
    asset_name: str | None
    asset_type: str
    broker: str
    prev_quantity: Decimal | None
    curr_quantity: Decimal | None
    prev_value_hkd: Decimal | None
    curr_value_hkd: Decimal | None
    value_change_hkd: Decimal | None
    status: str  # "new", "closed", "increased", "decreased", "unchanged"


@router.get("/snapshots", response_model=list[MonthlyNAV])
async def get_nav_history(db: AsyncSession = Depends(get_db)):
    """Monthly NAV history across all accounts with weekend fill-forward for Futu."""
    result = await db.execute(
        select(PositionSnapshot)
        .options(selectinload(PositionSnapshot.account), selectinload(PositionSnapshot.asset))
        .order_by(PositionSnapshot.snapshot_date)
    )
    snapshots = result.scalars().all()

    # Group by date, then by broker
    by_date_broker: dict[date, dict[str, Decimal]] = {}
    by_date_type: dict[date, dict[str, Decimal]] = {}

    for snap in snapshots:
        d = snap.snapshot_date
        broker = snap.account.broker.value if snap.account else "unknown"
        atype = snap.asset.asset_type.value if snap.asset else "unknown"
        val = snap.market_value_hkd or Decimal("0")

        if d not in by_date_broker:
            by_date_broker[d] = {}
            by_date_type[d] = {}

        by_date_broker[d][broker] = by_date_broker[d].get(broker, Decimal("0")) + val
        by_date_type[d][atype] = by_date_type[d].get(atype, Decimal("0")) + val

    # Sort all dates and apply fill-forward for Futu on weekends
    all_dates = sorted(by_date_broker.keys())

    # Track last-known Futu value and its date for fill-forward
    futu_last_value: Decimal | None = None
    futu_last_date: date | None = None

    monthly: list[MonthlyNAV] = []

    for snap_date in all_dates:
        by_broker: dict[str, BrokerValue] = {}
        by_type = by_date_type.get(snap_date, {})

        # Get actual data for this date
        actual_brokers = by_date_broker.get(snap_date, {})

        # Check if today is a weekend (Saturday=5, Sunday=6)
        weekday = snap_date.weekday()
        is_weekend = weekday >= 5

        # Process each broker
        for broker in actual_brokers:
            val = actual_brokers[broker]
            by_broker[broker] = BrokerValue(
                value_hkd=val,
                source="actual",
                as_of_date=None,
            )
            # Update Futu's last known value if this is Futu data
            if broker == "futu":
                futu_last_value = val
                futu_last_date = snap_date

        # Apply weekend fill-forward for Futu if missing
        if is_weekend and "futu" not in actual_brokers and futu_last_value is not None:
            by_broker["futu"] = BrokerValue(
                value_hkd=futu_last_value,
                source="filled_forward",
                as_of_date=futu_last_date,
            )

        # Calculate total NAV (sum of all broker values)
        total = sum(bv.value_hkd for bv in by_broker.values()) + sum(by_type.values()) - sum(by_broker.values())
        # Actually: total should be sum of all brokers + sum of cash (if in by_type but not in by_broker)
        # Simpler: just sum all broker values (which are already summed by date above)
        total = Decimal("0")
        for broker_vals in by_broker.values():
            total += broker_vals.value_hkd

        monthly.append(MonthlyNAV(
            snapshot_date=snap_date,
            total_nav_hkd=total,
            by_broker=by_broker,
            by_asset_type=by_type,
        ))

    return monthly


@router.get("/changes", response_model=list[PositionChange])
async def get_position_changes(db: AsyncSession = Depends(get_db)):
    """
    Compare the two most recent snapshot dates and return what changed.
    Shows new positions, closed positions, and size/value changes.
    """
    # Get the two most recent snapshot dates
    dates_result = await db.execute(
        select(PositionSnapshot.snapshot_date)
        .distinct()
        .order_by(PositionSnapshot.snapshot_date.desc())
        .limit(2)
    )
    dates = [row[0] for row in dates_result.fetchall()]

    if len(dates) < 2:
        return []  # Need at least 2 snapshots to compare

    curr_date, prev_date = dates[0], dates[1]

    # Fetch both snapshots
    async def fetch_snaps(d: date) -> dict[tuple, PositionSnapshot]:
        res = await db.execute(
            select(PositionSnapshot)
            .options(selectinload(PositionSnapshot.account), selectinload(PositionSnapshot.asset))
            .where(PositionSnapshot.snapshot_date == d)
        )
        return {(s.account_id, s.asset_id): s for s in res.scalars().all()}

    curr_snaps = await fetch_snaps(curr_date)
    prev_snaps = await fetch_snaps(prev_date)

    all_keys = set(curr_snaps) | set(prev_snaps)
    changes: list[PositionChange] = []

    for key in all_keys:
        curr = curr_snaps.get(key)
        prev = prev_snaps.get(key)

        snap = curr or prev
        symbol = snap.asset.symbol if snap.asset else ""
        name = snap.asset.name if snap.asset else None
        atype = snap.asset.asset_type.value if snap.asset else "unknown"
        broker = snap.account.broker.value if snap.account else "unknown"

        prev_qty = prev.quantity if prev else None
        curr_qty = curr.quantity if curr else None
        prev_val = prev.market_value_hkd if prev else None
        curr_val = curr.market_value_hkd if curr else None
        val_change = (curr_val or Decimal("0")) - (prev_val or Decimal("0"))

        if prev is None:
            status = "new"
        elif curr is None or curr_qty == Decimal("0"):
            status = "closed"
        elif curr_qty > prev_qty:
            status = "increased"
        elif curr_qty < prev_qty:
            status = "decreased"
        else:
            status = "unchanged"

        changes.append(PositionChange(
            symbol=symbol,
            asset_name=name,
            asset_type=atype,
            broker=broker,
            prev_quantity=prev_qty,
            curr_quantity=curr_qty,
            prev_value_hkd=prev_val,
            curr_value_hkd=curr_val,
            value_change_hkd=val_change,
            status=status,
        ))

    # Sort: new/closed first, then by absolute value change
    changes.sort(key=lambda c: (
        c.status not in ("new", "closed"),
        -(abs(c.value_change_hkd) if c.value_change_hkd else Decimal("0"))
    ))

    return changes


@router.get("/snapshots/{snapshot_date}")
async def get_snapshot_detail(snapshot_date: date, db: AsyncSession = Depends(get_db)):
    """Full position breakdown for a specific snapshot date."""
    result = await db.execute(
        select(PositionSnapshot)
        .options(selectinload(PositionSnapshot.account), selectinload(PositionSnapshot.asset))
        .where(PositionSnapshot.snapshot_date == snapshot_date)
        .order_by(PositionSnapshot.market_value_hkd.desc().nulls_last())
    )
    snaps = result.scalars().all()

    return [
        {
            "symbol": s.asset.symbol if s.asset else "",
            "name": s.asset.name if s.asset else None,
            "asset_type": s.asset.asset_type.value if s.asset else "unknown",
            "broker": s.account.broker.value if s.account else "unknown",
            "quantity": s.quantity,
            "price_hkd": s.price_hkd,
            "market_value_hkd": s.market_value_hkd,
            "source_file": s.source_file,
        }
        for s in snaps
    ]
