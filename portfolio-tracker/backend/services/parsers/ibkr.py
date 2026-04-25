"""
IBKR Activity Statement parser.

IBKR PDFs follow a consistent section-based format. Key sections:
  - "Open Positions" — current holdings
  - "Trades" / "Transaction History" — buy/sell activity
  - "Dividends", "Fees", "Deposits & Withdrawals"

The parser handles both:
  (a) pdfplumber text output (structured lines)
  (b) Claude Vision output (pipe-delimited POSITION / TRANSACTION lines)
"""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from services.parsers.base import BrokerParser, ParsedStatement, RawPosition, RawTransaction


class IBKRParser(BrokerParser):
    broker_name = "ibkr"
    account_currency = "USD"

    def parse(self, text: str, tables: list, filename: str = "") -> ParsedStatement:
        statement = ParsedStatement(
            broker="ibkr",
            account_name=self._extract_account_name(text),
            statement_date=self._extract_statement_date(text),
            currency="USD",
        )

        # Claude Vision output (pipe-delimited)
        if "POSITION |" in text or "TRANSACTION |" in text:
            self._parse_vision_output(text, statement)
            return statement

        # pdfplumber structured text
        self._parse_positions_section(text, tables, statement)
        self._parse_trades_section(text, tables, statement)
        self._parse_cash_transactions(text, tables, statement)

        return statement

    # ── pdfplumber parsing ────────────────────────────────────────────────────

    def _parse_positions_section(self, text: str, tables: list, stmt: ParsedStatement) -> None:
        """
        IBKR Open Positions table columns:
        Symbol | Description | Mult | Position | Price | Value | Unrealized P&L
        """
        for table in tables:
            if not table or len(table) < 2:
                continue
            header = [str(c).strip().lower() if c else "" for c in table[0]]
            if "symbol" not in header or "position" not in header:
                continue

            sym_idx = header.index("symbol")
            desc_idx = header.index("description") if "description" in header else None
            qty_idx = header.index("position")
            price_idx = header.index("price") if "price" in header else None
            value_idx = header.index("value") if "value" in header else None

            for row in table[1:]:
                if not row or not row[sym_idx]:
                    continue
                symbol = str(row[sym_idx]).strip()
                if not symbol or symbol.lower() in ("symbol", "total"):
                    continue

                name = str(row[desc_idx]).strip() if desc_idx is not None and row[desc_idx] else None
                qty = self._safe_decimal(row[qty_idx] if qty_idx < len(row) else None)
                price = self._safe_decimal(row[price_idx] if price_idx is not None and price_idx < len(row) else None)
                value = self._safe_decimal(row[value_idx] if value_idx is not None and value_idx < len(row) else None)

                if qty == Decimal("0"):
                    continue

                stmt.positions.append(RawPosition(
                    symbol=symbol,
                    name=name,
                    quantity=qty,
                    price=price if price else None,
                    currency="USD",
                    market_value=value if value else None,
                    asset_type_hint=self._guess_asset_type(symbol, name),
                ))

    def _parse_trades_section(self, text: str, tables: list, stmt: ParsedStatement) -> None:
        """
        IBKR Trades table columns:
        Symbol | Date/Time | Quantity | T.Price | C.Price | Proceeds | Comm/Fee | Basis | Realized P&L | MTM P&L | Code
        """
        for table in tables:
            if not table or len(table) < 2:
                continue
            header = [str(c).strip().lower() if c else "" for c in table[0]]
            if "symbol" not in header:
                continue
            if not any(kw in " ".join(header) for kw in ("t.price", "proceeds", "quantity")):
                continue

            sym_idx = header.index("symbol")
            date_idx = next((i for i, h in enumerate(header) if "date" in h), None)
            qty_idx = header.index("quantity") if "quantity" in header else None
            price_idx = next((i for i, h in enumerate(header) if "t.price" in h or h == "price"), None)
            proceeds_idx = header.index("proceeds") if "proceeds" in header else None
            fee_idx = next((i for i, h in enumerate(header) if "comm" in h or "fee" in h), None)

            for row in table[1:]:
                if not row or not row[sym_idx]:
                    continue
                symbol = str(row[sym_idx]).strip()
                if not symbol or symbol.lower() in ("symbol", "total"):
                    continue

                qty_raw = self._safe_decimal(row[qty_idx] if qty_idx is not None else None)
                trade_date = self._safe_date(row[date_idx] if date_idx is not None and date_idx < len(row) else None)
                if not trade_date:
                    continue

                price = self._safe_decimal(row[price_idx] if price_idx is not None and price_idx < len(row) else None)
                proceeds = self._safe_decimal(row[proceeds_idx] if proceeds_idx is not None and proceeds_idx < len(row) else None)
                fee = abs(self._safe_decimal(row[fee_idx] if fee_idx is not None and fee_idx < len(row) else None))

                tx_type = "buy" if qty_raw > 0 else "sell"

                stmt.transactions.append(RawTransaction(
                    trade_date=trade_date,
                    tx_type=tx_type,
                    symbol=symbol,
                    quantity=abs(qty_raw),
                    price=price if price else None,
                    gross_amount=abs(proceeds) if proceeds else None,
                    fee=fee,
                    currency="USD",
                    asset_type_hint=self._guess_asset_type(symbol, None),
                ))

    def _parse_cash_transactions(self, text: str, tables: list, stmt: ParsedStatement) -> None:
        """Parse dividends, withholding taxes, fees."""
        # Keywords that should never be treated as ticker symbols
        NON_TICKER_KEYWORDS = {
            "DIVIDE", "DIVIDEND", "DIVIDENDS", "DIV",
            "WITHHOLDING", "WITHHOLDINGS", "TAX", "TAXES",
            "PAYMENT", "PAYMENTS", "CASH", "INTEREST",
            "FEE", "FEES", "EXPENSE", "WITHDRAW",
            "DEPOSIT"
        }

        for table in tables:
            if not table or len(table) < 2:
                continue
            header = [str(c).strip().lower() if c else "" for c in table[0]]
            if "description" not in header or "amount" not in header:
                continue

            date_idx = next((i for i, h in enumerate(header) if "date" in h), None)
            desc_idx = header.index("description")
            amount_idx = header.index("amount")

            for row in table[1:]:
                if not row or not row[desc_idx]:
                    continue
                desc = str(row[desc_idx]).strip().lower()
                amount = self._safe_decimal(row[amount_idx] if amount_idx < len(row) else None)
                trade_date = self._safe_date(row[date_idx] if date_idx is not None and date_idx < len(row) else None)

                if not trade_date or amount == Decimal("0"):
                    continue

                # Extract symbol from description (e.g. "AAPL(US...) Cash Dividend")
                # Try to match ticker symbol at start of description
                sym_match = re.match(r"^([A-Z]{1,5})\s*[\(\-]", desc.upper())
                symbol = sym_match.group(1) if sym_match else None

                # Guard: reject extracted symbols that are known non-ticker keywords
                if symbol and symbol.upper() in NON_TICKER_KEYWORDS:
                    symbol = None

                if "dividend" in desc:
                    tx_type = "dividend"
                elif "withholding" in desc or "tax" in desc:
                    tx_type = "fee"
                elif "deposit" in desc:
                    tx_type = "deposit"
                elif "withdrawal" in desc:
                    tx_type = "withdrawal"
                else:
                    tx_type = "fee"

                stmt.transactions.append(RawTransaction(
                    trade_date=trade_date,
                    tx_type=tx_type,
                    symbol=symbol,
                    quantity=None,
                    price=None,
                    gross_amount=amount,
                    fee=Decimal("0"),
                    currency="USD",
                    notes=str(row[desc_idx]),
                ))

    # ── Claude Vision output parsing ─────────────────────────────────────────

    def _parse_vision_output(self, text: str, stmt: ParsedStatement) -> None:
        for line in text.splitlines():
            parts = [p.strip() for p in line.split("|")]
            if not parts:
                continue
            if parts[0].upper() == "POSITION" and len(parts) >= 7:
                _, symbol, name, qty_s, price_s, currency, value_s = parts[:7]
                if not symbol:
                    continue
                stmt.positions.append(RawPosition(
                    symbol=symbol.upper(),
                    name=name or None,
                    quantity=self._safe_decimal(qty_s),
                    price=self._safe_decimal(price_s) or None,
                    currency=currency or "USD",
                    market_value=self._safe_decimal(value_s) or None,
                    asset_type_hint=self._guess_asset_type(symbol, name),
                ))
            elif parts[0].upper() == "TRANSACTION" and len(parts) >= 9:
                _, date_s, tx_type, symbol, qty_s, price_s, amount_s, fee_s, currency = parts[:9]
                trade_date = self._safe_date(date_s)
                if not trade_date:
                    continue
                stmt.transactions.append(RawTransaction(
                    trade_date=trade_date,
                    tx_type=tx_type.lower() or "buy",
                    symbol=symbol.upper() if symbol else None,
                    quantity=self._safe_decimal(qty_s) or None,
                    price=self._safe_decimal(price_s) or None,
                    gross_amount=self._safe_decimal(amount_s) or None,
                    fee=self._safe_decimal(fee_s),
                    currency=currency or "USD",
                ))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _extract_account_name(self, text: str) -> str | None:
        m = re.search(r"Account\s*(?:ID|Number)[:\s]+([A-Z0-9]+)", text)
        return m.group(1) if m else None

    def _extract_statement_date(self, text: str) -> date | None:
        m = re.search(r"Period:\s*[\w\s,]+-\s*([\w\s,]+\d{4})", text)
        if m:
            return self._safe_date(m.group(1))
        m = re.search(r"Statement\s*Date[:\s]+([\w\s,]+\d{4})", text)
        if m:
            return self._safe_date(m.group(1))
        return None

    def _guess_asset_type(self, symbol: str, name: str | None) -> str:
        sym = (symbol or "").upper()
        desc = (name or "").lower()
        if any(kw in desc for kw in ("etf", "fund", "index", "trust")):
            return "etf"
        if any(kw in desc for kw in ("treasury", "gilt", "bond", "note", "bill")):
            return "bond"
        if "." in sym and sym.endswith(("HK", "SS", "SZ")):
            return "stock"
        return "stock"  # IBKR is mostly stocks/ETFs
