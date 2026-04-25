"""
P&L summary and data quality endpoints.

GET  /pnl/summary        — estimated trading P&L by broker
GET  /pnl/data-quality   — per-broker data completeness
POST /pnl/recalculate    — recalculate all realized P&L from scratch (admin)
"""
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from database import get_db
from models.account import Account
from models.position import Position
from models.transaction import Transaction, TransactionTypeEnum
from services.pnl import recalculate_all_pnl
from services.data_quality import get_data_quality, BrokerDataQuality

router = APIRouter(prefix="/pnl", tags=["pnl"])


class BrokerPnlOut(BaseModel):
    broker: str
    realized_trading_pnl_hkd: Decimal | None
    unrealized_pnl_hkd: Decimal
    estimated_total_trading_pnl_hkd: Decimal | None
    dividend_income_hkd: Decimal | None
    fees_hkd: Decimal | None
    sells_total: int
    sells_included: int
    sells_excluded: int
    data_quality: str
    warnings: list[str]


class PnlTotals(BaseModel):
    realized_trading_pnl_hkd: Decimal | None
    unrealized_pnl_hkd: Decimal
    estimated_total_trading_pnl_hkd: Decimal | None
    dividend_income_hkd: Decimal | None
    fees_hkd: Decimal | None
    calculation_warnings: list[str]


class PnlSummary(BaseModel):
    by_broker: list[BrokerPnlOut]
    totals: PnlTotals


class DataQualityOut(BaseModel):
    broker: str
    trades: bool
    dividends: bool
    fees: bool
    deposits: bool
    withdrawals: bool
    cost_basis_reliability: str
    warnings: list[str]
    trade_count: int
    dividend_count: int
    fee_count: int
    deposit_count: int
    withdrawal_count: int
    earliest_trade_date: str | None
    sells_excluded_count: int


@router.get("/summary", response_model=PnlSummary)
async def get_pnl_summary(db: AsyncSession = Depends(get_db)) -> PnlSummary:
    # ── Realized P&L (sells only, included rows) ──────────────────────────
    realized_result = await db.execute(
        select(
            Account.broker,
            func.sum(Transaction.realized_pnl_hkd).label("realized"),
            func.count(Transaction.id).label("total_sells"),
            func.sum(
                func.cast(~Transaction.exclude_from_pnl_totals, __import__("sqlalchemy").Integer)
            ).label("included_sells"),
        )
        .join(Account, Transaction.account_id == Account.id)
        .where(Transaction.tx_type == TransactionTypeEnum.SELL)
        .group_by(Account.broker)
    )
    realized_by_broker = {
        str(r.broker): {
            "realized": r.realized,
            "total": int(r.total_sells or 0),
            "included": int(r.included_sells or 0),
        }
        for r in realized_result
    }

    # ── Unrealized P&L (current positions) ───────────────────────────────
    unreal_result = await db.execute(
        select(
            Account.broker,
            func.sum(Position.unrealized_pnl_hkd).label("unrealized"),
        )
        .join(Account, Position.account_id == Account.id)
        .where(Position.quantity > 0)
        .group_by(Account.broker)
    )
    unrealized_by_broker = {
        str(r.broker): r.unrealized or Decimal("0")
        for r in unreal_result
    }

    # ── Dividend income and fees (IBKR only currently) ────────────────────
    income_result = await db.execute(
        select(
            Account.broker,
            Transaction.tx_type,
            func.sum(Transaction.net_amount_hkd).label("total"),
        )
        .join(Account, Transaction.account_id == Account.id)
        .where(
            Transaction.tx_type.in_([TransactionTypeEnum.DIVIDEND, TransactionTypeEnum.FEE])
        )
        .group_by(Account.broker, Transaction.tx_type)
    )
    dividends_by_broker: dict[str, Decimal] = {}
    fees_by_broker: dict[str, Decimal] = {}
    for r in income_result:
        broker = str(r.broker)
        if str(r.tx_type) == "dividend":
            dividends_by_broker[broker] = r.total or Decimal("0")
        elif str(r.tx_type) == "fee":
            fees_by_broker[broker] = r.total or Decimal("0")

    # ── Data quality info ─────────────────────────────────────────────────
    dq_list = await get_data_quality(db)
    dq_by_broker = {dq.broker: dq for dq in dq_list}

    # ── Build per-broker output ───────────────────────────────────────────
    all_brokers = set(realized_by_broker) | set(unrealized_by_broker)
    broker_rows: list[BrokerPnlOut] = []

    for broker in sorted(all_brokers):
        r = realized_by_broker.get(broker, {"realized": None, "total": 0, "included": 0})
        unreal = unrealized_by_broker.get(broker, Decimal("0"))
        realized = r["realized"]
        total_sells = r["total"]
        included_sells = r["included"]
        excluded_sells = total_sells - included_sells

        estimated = (
            (realized or Decimal("0")) + unreal
            if realized is not None else None
        )

        dq = dq_by_broker.get(broker)
        broker_rows.append(BrokerPnlOut(
            broker=broker,
            realized_trading_pnl_hkd=realized,
            unrealized_pnl_hkd=unreal,
            estimated_total_trading_pnl_hkd=estimated,
            dividend_income_hkd=dividends_by_broker.get(broker),
            fees_hkd=fees_by_broker.get(broker),
            sells_total=total_sells,
            sells_included=included_sells,
            sells_excluded=excluded_sells,
            data_quality=dq.cost_basis_reliability if dq else "unknown",
            warnings=dq.warnings if dq else [],
        ))

    # ── Totals ────────────────────────────────────────────────────────────
    def _sum_optional(vals: list) -> Decimal | None:
        non_null = [v for v in vals if v is not None]
        return sum(non_null, Decimal("0")) if non_null else None

    total_realized = _sum_optional([r.realized_trading_pnl_hkd for r in broker_rows])
    total_unreal = sum(r.unrealized_pnl_hkd for r in broker_rows)
    total_estimated = (
        (total_realized or Decimal("0")) + total_unreal
        if total_realized is not None else None
    )

    incomplete_brokers = [
        b.broker for b in broker_rows if b.data_quality != "high"
    ]
    calc_warnings: list[str] = [
        "Estimated trading P&L only. This is not a true investment return.",
        "Unrealized P&L is mark-to-market at latest price — it does not reflect actual gains until sold.",
    ]
    if incomplete_brokers:
        calc_warnings.append(
            f"Dividends, fees, deposits, and withdrawals may be incomplete or missing for: "
            f"{', '.join(b.upper() for b in incomplete_brokers)}."
        )

    totals = PnlTotals(
        realized_trading_pnl_hkd=total_realized,
        unrealized_pnl_hkd=total_unreal,
        estimated_total_trading_pnl_hkd=total_estimated,
        dividend_income_hkd=_sum_optional(list(dividends_by_broker.values())),
        fees_hkd=_sum_optional(list(fees_by_broker.values())),
        calculation_warnings=calc_warnings,
    )

    return PnlSummary(by_broker=broker_rows, totals=totals)


@router.get("/data-quality", response_model=list[DataQualityOut])
async def get_data_quality_endpoint(db: AsyncSession = Depends(get_db)):
    dq_list = await get_data_quality(db)
    return [
        DataQualityOut(
            broker=dq.broker,
            trades=dq.trades,
            dividends=dq.dividends,
            fees=dq.fees,
            deposits=dq.deposits,
            withdrawals=dq.withdrawals,
            cost_basis_reliability=dq.cost_basis_reliability,
            warnings=dq.warnings,
            trade_count=dq.trade_count,
            dividend_count=dq.dividend_count,
            fee_count=dq.fee_count,
            deposit_count=dq.deposit_count,
            withdrawal_count=dq.withdrawal_count,
            earliest_trade_date=dq.earliest_trade_date,
            sells_excluded_count=dq.sells_excluded_count,
        )
        for dq in dq_list
    ]


@router.post("/recalculate")
async def recalculate_pnl(db: AsyncSession = Depends(get_db)):
    """Recalculate all realized P&L from scratch. Idempotent. Requires API key."""
    groups_processed = await recalculate_all_pnl(db)
    await db.commit()
    return {"groups_processed": groups_processed, "status": "ok"}
