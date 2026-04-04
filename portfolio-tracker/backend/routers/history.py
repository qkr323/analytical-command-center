"""
Portfolio history endpoints.

GET /history/snapshots          — monthly NAV snapshots (all accounts combined)
GET /history/changes            — month-over-month position changes
GET /history/snapshots/{date}   — full position breakdown on a specific date
"""
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from database import get_db
from models.position_snapshot import PositionSnapshot

router = APIRouter(prefix="/history", tags=["history"])


class MonthlyNAV(BaseModel):
    snapshot_date: date
    total_nav_hkd: Decimal
    by_broker: dict[str, Decimal]
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
    """Monthly NAV history across all accounts."""
    result = await db.execute(
        select(PositionSnapshot)
        .options(selectinload(PositionSnapshot.account), selectinload(PositionSnapshot.asset))
        .order_by(PositionSnapshot.snapshot_date)
    )
    snapshots = result.scalars().all()

    # Group by date
    by_date: dict[date, list[PositionSnapshot]] = {}
    for snap in snapshots:
        by_date.setdefault(snap.snapshot_date, []).append(snap)

    monthly: list[MonthlyNAV] = []
    for snap_date, snaps in sorted(by_date.items()):
        total = Decimal("0")
        by_broker: dict[str, Decimal] = {}
        by_type: dict[str, Decimal] = {}

        for s in snaps:
            val = s.market_value_hkd or Decimal("0")
            total += val
            broker = s.account.broker.value if s.account else "unknown"
            atype = s.asset.asset_type.value if s.asset else "unknown"
            by_broker[broker] = by_broker.get(broker, Decimal("0")) + val
            by_type[atype] = by_type.get(atype, Decimal("0")) + val

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
