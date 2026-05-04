"""
Rebuild 30-day position history from transactions.

When snapshots are missing for certain days (no sync data), this service:
1. Deletes position_snapshots for the last N days
2. Replays transactions from the opening snapshot
3. Forward-fills positions with historical prices
4. Writes clean daily snapshots for the entire window

Called automatically at the end of every IBKR and PDF upload sync.
"""
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.position_snapshot import PositionSnapshot
from models.transaction import Transaction, TransactionTypeEnum
from models.asset import Asset
from models.account import Account
from services.fx import convert_to_hkd, refresh_rates
from services.prices import fetch_historical_prices


async def rebuild_position_history(db: AsyncSession, days: int = 30) -> dict[str, Any]:
    """
    Rebuild position snapshots for the last N days.

    Deletes existing snapshots in the window, replays transactions,
    forward-fills positions with historical prices.

    Returns: {"days_rebuilt": int, "snapshots_created": int}
    """
    today = date.today()
    start_date = today - timedelta(days=days)

    # ─── Step 1: Delete snapshots in the window ───────────────────────────────────
    await db.execute(
        delete(PositionSnapshot).where(PositionSnapshot.snapshot_date >= start_date)
    )
    await db.flush()

    # ─── Step 2: Get opening positions (just before the window) ───────────────────
    opening_snaps = await db.execute(
        select(PositionSnapshot)
        .where(PositionSnapshot.snapshot_date < start_date)
        .order_by(PositionSnapshot.snapshot_date.desc())
    )
    opening_snaps_list = opening_snaps.scalars().all()

    # De-duplicate by (account_id, asset_id), keeping the most recent
    # Extract data into simple dicts to avoid SQLAlchemy ORM expiration issues
    opening_positions: dict[tuple[int, int], dict[str, Any]] = {}
    for snap in opening_snaps_list:
        key = (snap.account_id, snap.asset_id)
        if key not in opening_positions:
            opening_positions[key] = {
                "quantity": snap.quantity,
                "price_hkd": snap.price_hkd,
            }

    # ─── Step 3: Load all transactions in the window ────────────────────────────
    txn_result = await db.execute(
        select(Transaction)
        .where(Transaction.trade_date >= start_date, Transaction.trade_date <= today)
        .order_by(Transaction.trade_date, Transaction.id)
    )
    transactions = txn_result.scalars().all()

    # Group by day, then by (account_id, asset_id)
    txns_by_day: dict[date, dict[tuple[int, int], list[Transaction]]] = {}
    for txn in transactions:
        d = txn.trade_date
        key = (txn.account_id, txn.asset_id)
        if d not in txns_by_day:
            txns_by_day[d] = {}
        if key not in txns_by_day[d]:
            txns_by_day[d][key] = []
        txns_by_day[d][key].append(txn)

    # ─── Step 4: Batch-fetch historical prices ──────────────────────────────────
    # Get all asset IDs we'll need prices for
    # opening_positions keys are (account_id, asset_id) tuples, extract just asset_ids
    opening_asset_ids = {k[1] for k in opening_positions.keys()}
    all_asset_ids = opening_asset_ids | {txn.asset_id for txn in transactions}
    asset_ids_list = list(all_asset_ids)

    price_cache = await fetch_historical_prices(db, asset_ids_list, start_date, today)

    # ─── Step 5: Rebuild snapshots day by day ───────────────────────────────────
    # Initialize running positions from opening snapshot
    running_positions: dict[tuple[int, int], dict[str, Any]] = {}
    for key, snap_data in opening_positions.items():
        account_id, asset_id = key
        running_positions[key] = {
            "account_id": account_id,
            "asset_id": asset_id,
            "quantity": snap_data["quantity"],
            "asset": None,  # Will be lazy-loaded
            "last_price_native": snap_data["price_hkd"],  # Placeholder, will update
            "currency": "USD",  # Will update
        }

    # Lazy-load assets and currencies once
    assets: dict[int, Asset] = {}

    snapshots_created = 0

    for day_offset in range(days + 1):
        d = start_date + timedelta(days=day_offset)

        # Apply transactions for this day
        day_txns = txns_by_day.get(d, {})
        for key, day_txn_list in day_txns.items():
            account_id, asset_id = key
            for txn in day_txn_list:
                # Lazy-load asset if needed
                if asset_id not in assets:
                    asset_obj = await db.scalar(select(Asset).where(Asset.id == asset_id))
                    assets[asset_id] = asset_obj

                asset_obj = assets[asset_id]
                if asset_id not in [k[1] for k in running_positions]:
                    # New position
                    running_positions[key] = {
                        "account_id": account_id,
                        "asset_id": asset_id,
                        "quantity": Decimal("0"),
                        "asset": asset_obj,
                        "last_price_native": Decimal("1"),
                        "currency": txn.currency or "USD",
                    }

                # Apply transaction
                if txn.tx_type in (TransactionTypeEnum.BUY, TransactionTypeEnum.TRANSFER_IN):
                    running_positions[key]["quantity"] += txn.quantity
                elif txn.tx_type in (TransactionTypeEnum.SELL, TransactionTypeEnum.TRANSFER_OUT):
                    running_positions[key]["quantity"] -= txn.quantity

                running_positions[key]["currency"] = txn.currency or "USD"

        # Prune closed positions (qty <= 0)
        closed_keys = [k for k, pos in running_positions.items() if pos["quantity"] <= 0]
        for k in closed_keys:
            del running_positions[k]

        # Write snapshots for all active positions
        for (account_id, asset_id), pos in list(running_positions.items()):
            if asset_id not in assets:
                asset_obj = await db.scalar(select(Asset).where(Asset.id == asset_id))
                assets[asset_id] = asset_obj

            asset_obj = assets[asset_id]

            # Get price for this day
            price_native = price_cache.get(asset_id, {}).get(d)
            if price_native is None:
                # Fall back to last known price
                opening_pos = opening_positions.get((account_id, asset_id))
                price_native = opening_pos["price_hkd"] if opening_pos else Decimal("1")

            # Convert to HKD using historical FX rate
            price_hkd, _ = await convert_to_hkd(
                db, price_native, pos["currency"], rate_date=d
            )

            value_hkd = price_hkd * pos["quantity"]

            db.add(PositionSnapshot(
                snapshot_date=d,
                account_id=account_id,
                asset_id=asset_id,
                quantity=pos["quantity"],
                price_hkd=price_hkd,
                market_value_hkd=value_hkd,
                source_file="history_rebuild",
            ))

            snapshots_created += 1

        # Pre-warm FX cache for next day
        await refresh_rates(db, d)

    return {
        "days_rebuilt": days + 1,
        "snapshots_created": snapshots_created,
    }
