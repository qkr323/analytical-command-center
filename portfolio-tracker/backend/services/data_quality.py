"""
Per-broker data completeness definitions.

Static: what each broker's parser/API can currently provide.
Dynamic: actual transaction counts queried at runtime.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.account import Account
from models.transaction import Transaction, TransactionTypeEnum


@dataclass
class BrokerDataQuality:
    broker: str
    trades: bool
    dividends: bool
    fees: bool
    deposits: bool
    withdrawals: bool
    cost_basis_reliability: str   # "high", "partial", "experimental"
    warnings: list[str] = field(default_factory=list)

    # Populated dynamically
    trade_count: int = 0
    dividend_count: int = 0
    fee_count: int = 0
    deposit_count: int = 0
    withdrawal_count: int = 0
    earliest_trade_date: str | None = None
    sells_excluded_count: int = 0  # sells with exclude_from_pnl_totals=True


# Static capability definitions — reflects current parser/API support
_STATIC: dict[str, BrokerDataQuality] = {
    "ibkr": BrokerDataQuality(
        broker="ibkr",
        trades=True,
        dividends=True,
        fees=True,
        deposits=True,
        withdrawals=True,
        cost_basis_reliability="high",
        warnings=[],
    ),
    "futu": BrokerDataQuality(
        broker="futu",
        trades=True,
        dividends=False,
        fees=False,
        deposits=False,
        withdrawals=False,
        cost_basis_reliability="partial",
        warnings=[
            "Dividends not imported from Futu PDF statements.",
            "Fees not imported — P&L may be slightly overstated.",
            "Deposits and withdrawals not available — cash flows excluded.",
            "Trade history begins from when PDF sync was set up (Apr 2026). "
            "Earlier trades may be missing, affecting cost basis.",
        ],
    ),
    "sofi": BrokerDataQuality(
        broker="sofi",
        trades=True,
        dividends=False,
        fees=False,
        deposits=False,
        withdrawals=False,
        cost_basis_reliability="partial",
        warnings=[
            "Dividends, fees, and cash flows not imported from SoFi PDF statements.",
            "Cost basis reliability depends on completeness of imported trade history.",
        ],
    ),
    "hangseng": BrokerDataQuality(
        broker="hangseng",
        trades=True,
        dividends=False,
        fees=False,
        deposits=False,
        withdrawals=False,
        cost_basis_reliability="partial",
        warnings=[
            "Dividends, fees, and cash flows not imported from Hang Seng PDF statements.",
            "Monthly PDF upload only — gaps between statements may affect cost basis.",
        ],
    ),
    "osl": BrokerDataQuality(
        broker="osl",
        trades=True,
        dividends=False,
        fees=False,
        deposits=False,
        withdrawals=False,
        cost_basis_reliability="partial",
        warnings=[
            "Dividends, fees, and cash flows not imported from OSL PDF statements.",
            "Monthly PDF upload only — trade history may be incomplete.",
        ],
    ),
    "binance": BrokerDataQuality(
        broker="binance",
        trades=True,
        dividends=False,
        fees=False,
        deposits=False,
        withdrawals=False,
        cost_basis_reliability="experimental",
        warnings=[
            "Trade P&L only. Binance API history may be incomplete (90-day rolling window "
            "for some endpoints).",
            "Fees not currently imported — P&L may be slightly overstated.",
            "Treat Binance P&L as indicative only.",
        ],
    ),
}


async def get_data_quality(db: AsyncSession) -> list[BrokerDataQuality]:
    """Return per-broker data quality with dynamic transaction counts filled in."""

    # Query transaction counts by broker and type
    result = await db.execute(
        select(
            Account.broker,
            Transaction.tx_type,
            func.count(Transaction.id).label("cnt"),
            func.min(Transaction.trade_date).label("earliest"),
        )
        .join(Account, Transaction.account_id == Account.id)
        .group_by(Account.broker, Transaction.tx_type)
    )
    rows = result.all()

    # Query excluded sell counts per broker
    excluded_result = await db.execute(
        select(Account.broker, func.count(Transaction.id).label("cnt"))
        .join(Account, Transaction.account_id == Account.id)
        .where(
            Transaction.tx_type == TransactionTypeEnum.SELL,
            Transaction.exclude_from_pnl_totals == True,  # noqa: E712
        )
        .group_by(Account.broker)
    )
    excluded_by_broker = {str(r.broker): r.cnt for r in excluded_result}

    # Build lookup
    counts: dict[str, dict] = {}
    earliest: dict[str, str] = {}
    for row in rows:
        broker = str(row.broker)
        if broker not in counts:
            counts[broker] = {}
        counts[broker][str(row.tx_type)] = row.cnt
        if row.earliest:
            prev = earliest.get(broker)
            date_str = str(row.earliest)
            if prev is None or date_str < prev:
                earliest[broker] = date_str

    # Build output — known brokers first, then any extras in the DB
    known = set(_STATIC.keys())
    all_brokers = list(known) + [b for b in counts if b not in known]

    output: list[BrokerDataQuality] = []
    for broker in all_brokers:
        base = _STATIC.get(broker)
        if base is None:
            base = BrokerDataQuality(
                broker=broker,
                trades=True,
                dividends=False,
                fees=False,
                deposits=False,
                withdrawals=False,
                cost_basis_reliability="unknown",
                warnings=["Broker not in data quality registry."],
            )
        import copy
        dq = copy.deepcopy(base)
        bc = counts.get(broker, {})
        dq.trade_count      = bc.get("buy", 0) + bc.get("sell", 0)
        dq.dividend_count   = bc.get("dividend", 0)
        dq.fee_count        = bc.get("fee", 0)
        dq.deposit_count    = bc.get("deposit", 0)
        dq.withdrawal_count = bc.get("withdrawal", 0)
        dq.earliest_trade_date = earliest.get(broker)
        dq.sells_excluded_count = excluded_by_broker.get(broker, 0)
        output.append(dq)

    return output
