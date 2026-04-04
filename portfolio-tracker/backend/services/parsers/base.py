from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass
class RawPosition:
    symbol: str
    name: str | None
    quantity: Decimal
    price: Decimal | None
    currency: str
    market_value: Decimal | None = None
    asset_type_hint: str | None = None   # "stock", "etf", "crypto", "bond"


@dataclass
class RawTransaction:
    trade_date: date
    tx_type: str           # "buy", "sell", "dividend", "fee", "deposit", "withdrawal"
    symbol: str | None
    quantity: Decimal | None
    price: Decimal | None
    gross_amount: Decimal | None
    fee: Decimal
    currency: str
    notes: str | None = None
    asset_type_hint: str | None = None


@dataclass
class ParsedStatement:
    broker: str
    account_name: str | None
    statement_date: date | None
    currency: str
    positions: list[RawPosition] = field(default_factory=list)
    transactions: list[RawTransaction] = field(default_factory=list)
    parse_warnings: list[str] = field(default_factory=list)


class BrokerParser:
    broker_name: str = "unknown"
    account_currency: str = "USD"

    def parse(
        self,
        text: str,
        tables: list[list[list[str | None]]],
        filename: str = "",
    ) -> ParsedStatement:
        raise NotImplementedError

    def _safe_decimal(self, value: str | None, default: Decimal = Decimal("0")) -> Decimal:
        if not value:
            return default
        cleaned = str(value).replace(",", "").replace("$", "").replace("HK$", "").strip()
        if cleaned in ("", "-", "N/A", "n/a"):
            return default
        try:
            return Decimal(cleaned)
        except Exception:
            return default

    def _safe_date(self, value: str | None) -> date | None:
        if not value:
            return None
        from dateutil import parser as dateutil_parser
        try:
            return dateutil_parser.parse(str(value).strip()).date()
        except Exception:
            return None
