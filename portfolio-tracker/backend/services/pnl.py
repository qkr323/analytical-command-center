"""
Realized P&L calculation service — average cost method, v1.

Grouping key: (account_id, asset_id, currency)
Processes all BUY/SELL transactions for a group chronologically,
maintaining running average cost in both local currency and HKD.

Data quality flags:
  ok                — all data available, P&L reliable
  no_cost_basis     — no buy history found; sell excluded from totals
  partial_history   — sold more shares than recorded; excluded from totals
  partial_hkd_basis — HKD cost basis incomplete (FX missing on some buys); included with caveat
  no_hkd_fx         — cannot compute HKD P&L at all; excluded from totals
  fx_estimated      — used nearest available FX (not trade-date); included with caveat
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.transaction import Transaction, TransactionTypeEnum

CALCULATION_VERSION = "1.0"
COST_BASIS_METHOD = "average_cost_v1"

# Flags that mean P&L is unreliable and must be excluded from totals
_EXCLUDE_FLAGS = {"no_cost_basis", "partial_history", "no_hkd_fx"}


@dataclass
class _RunningState:
    qty: Decimal = field(default_factory=lambda: Decimal("0"))
    avg_cost_local: Decimal = field(default_factory=lambda: Decimal("0"))
    avg_cost_hkd: Decimal | None = None  # None = FX unavailable on at least one buy in chain


def _process_buy(tx: Transaction, state: _RunningState) -> None:
    qty = tx.quantity or Decimal("0")
    if qty <= 0:
        return

    fee_local = tx.fee or Decimal("0")
    gross_local = tx.gross_amount or (qty * (tx.price or Decimal("0")))
    buy_cost_local = gross_local + fee_local

    new_qty = state.qty + qty

    # Update local running average
    state.avg_cost_local = (
        (state.qty * state.avg_cost_local + buy_cost_local) / new_qty
        if new_qty > 0 else Decimal("0")
    )

    # Update HKD running average — only when HKD data is available and unbroken
    gross_hkd = tx.gross_amount_hkd
    fee_hkd = tx.fee_hkd or Decimal("0")

    if gross_hkd is not None:
        buy_cost_hkd = gross_hkd + fee_hkd
        if state.qty == Decimal("0"):
            # Fresh start — initialize HKD avg cost
            state.avg_cost_hkd = buy_cost_hkd / qty
        elif state.avg_cost_hkd is not None:
            # HKD chain is intact — update it
            state.avg_cost_hkd = (
                (state.qty * state.avg_cost_hkd + buy_cost_hkd) / new_qty
            )
        # else: chain already broken (prior buy had no HKD) — leave as None
    else:
        # This buy has no HKD data — break the HKD chain
        state.avg_cost_hkd = None

    state.qty = new_qty


def _process_sell(tx: Transaction, state: _RunningState, now: datetime) -> None:
    qty = tx.quantity or Decimal("0")
    if qty <= 0:
        return

    # Stamp audit fields on every sell regardless of outcome
    tx.cost_basis_method = COST_BASIS_METHOD
    tx.calculation_version = CALCULATION_VERSION
    tx.pnl_calculated_at = now

    fee_local = tx.fee or Decimal("0")
    fee_hkd = tx.fee_hkd or Decimal("0")

    # ── No cost basis ────────────────────────────────────────────────────────
    if state.qty <= 0 or state.avg_cost_local <= 0:
        tx.data_quality_flag = "no_cost_basis"
        tx.exclude_from_pnl_totals = True
        tx.realized_pnl_local = None
        tx.realized_pnl_hkd = None
        tx.cost_basis_local = None
        tx.cost_basis_hkd = None
        return

    # ── Partial history (sold more than recorded) ─────────────────────────
    if qty > state.qty:
        tx.data_quality_flag = "partial_history"
        tx.exclude_from_pnl_totals = True
        tx.realized_pnl_local = None
        tx.realized_pnl_hkd = None
        tx.cost_basis_local = None
        tx.cost_basis_hkd = None
        # Drain the position
        state.qty = Decimal("0")
        state.avg_cost_local = Decimal("0")
        state.avg_cost_hkd = None
        return

    # ── Calculate local P&L ──────────────────────────────────────────────
    cost_basis_local = qty * state.avg_cost_local
    gross_local = tx.gross_amount or (qty * (tx.price or Decimal("0")))
    realized_pnl_local = gross_local - cost_basis_local - fee_local

    tx.cost_basis_local = cost_basis_local
    tx.avg_cost_per_unit_local = state.avg_cost_local
    tx.realized_pnl_local = realized_pnl_local

    # ── Calculate HKD P&L ────────────────────────────────────────────────
    gross_hkd = tx.gross_amount_hkd

    if state.avg_cost_hkd is not None and gross_hkd is not None:
        # Full HKD data available — proper calculation
        cost_basis_hkd = qty * state.avg_cost_hkd
        realized_pnl_hkd = gross_hkd - cost_basis_hkd - fee_hkd
        tx.cost_basis_hkd = cost_basis_hkd
        tx.avg_cost_per_unit_hkd = state.avg_cost_hkd
        tx.realized_pnl_hkd = realized_pnl_hkd
        tx.data_quality_flag = "ok"
        tx.exclude_from_pnl_totals = False

    elif state.avg_cost_hkd is None and gross_hkd is not None and tx.fx_rate_to_hkd:
        # HKD cost basis broken — estimate cost basis using sell-date FX
        cost_basis_hkd = cost_basis_local * tx.fx_rate_to_hkd
        realized_pnl_hkd = gross_hkd - cost_basis_hkd - fee_hkd
        tx.cost_basis_hkd = cost_basis_hkd
        tx.avg_cost_per_unit_hkd = None  # estimated, not tracked
        tx.realized_pnl_hkd = realized_pnl_hkd
        tx.data_quality_flag = "partial_hkd_basis"
        tx.exclude_from_pnl_totals = False

    else:
        # Cannot compute HKD P&L
        tx.cost_basis_hkd = None
        tx.avg_cost_per_unit_hkd = None
        tx.realized_pnl_hkd = None
        tx.data_quality_flag = "no_hkd_fx"
        tx.exclude_from_pnl_totals = True

    # ── Update running state (average cost unchanged on sell) ────────────
    state.qty -= qty
    if state.qty <= Decimal("0"):
        state.qty = Decimal("0")
        state.avg_cost_local = Decimal("0")
        state.avg_cost_hkd = None


async def recalculate_pnl_for_group(
    db: AsyncSession,
    account_id: int,
    asset_id: int,
    currency: str,
) -> None:
    """Recalculate realized P&L for one (account, asset, currency) group.

    Always replays the full transaction history from the beginning.
    Safe to call multiple times — result is deterministic given the same transactions.
    """
    result = await db.execute(
        select(Transaction)
        .where(
            Transaction.account_id == account_id,
            Transaction.asset_id == asset_id,
            Transaction.currency == currency,
            Transaction.tx_type.in_([TransactionTypeEnum.BUY, TransactionTypeEnum.SELL]),
        )
        .order_by(Transaction.trade_date.asc(), Transaction.id.asc())
    )
    txs = result.scalars().all()
    if not txs:
        return

    state = _RunningState()
    now = datetime.now(timezone.utc)

    for tx in txs:
        if tx.tx_type == TransactionTypeEnum.BUY:
            _process_buy(tx, state)
        elif tx.tx_type == TransactionTypeEnum.SELL:
            _process_sell(tx, state, now)


async def recalculate_pnl_for_pairs(
    db: AsyncSession,
    pairs: set[tuple[int, int, str]],
) -> None:
    """Recalculate a batch of (account_id, asset_id, currency) pairs.

    Called at the end of each upload or sync.  Does not commit — caller commits.
    """
    for (account_id, asset_id, currency) in pairs:
        await recalculate_pnl_for_group(db, account_id, asset_id, currency)


async def recalculate_all_pnl(db: AsyncSession) -> int:
    """Recalculate P&L for every (account, asset, currency) group in the database.

    Used by POST /pnl/recalculate. Returns number of groups processed.
    """
    result = await db.execute(
        select(
            Transaction.account_id,
            Transaction.asset_id,
            Transaction.currency,
        )
        .where(
            Transaction.asset_id.is_not(None),
            Transaction.tx_type.in_([TransactionTypeEnum.BUY, TransactionTypeEnum.SELL]),
        )
        .distinct()
    )
    pairs = {(r.account_id, r.asset_id, r.currency) for r in result}
    for (account_id, asset_id, currency) in pairs:
        await recalculate_pnl_for_group(db, account_id, asset_id, currency)
    return len(pairs)
