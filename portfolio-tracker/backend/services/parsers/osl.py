"""
OSL Digital Securities Limited statement parser.

Statement sections:
  1A. Account Balance Summary (month-end holdings):
      Currency | Opening Balance | Net Movement | Closing Balance | Closing Price (USD) | Market Value (USD)

  2B. Trade Transactions:
      Date | Tx Type | Trade State | Buy/Sell | Currency | Qty | Executed Price | Consideration CCY | Consideration | Fee | Trade Ref

Date format in transactions: DD/MM/YYYY HH:MM
All trades have consideration in HKD (no USD trades observed).
Fees are typically 0.00.
"""
from __future__ import annotations

import re
from decimal import Decimal
from datetime import datetime

from services.parsers.base import BrokerParser, ParsedStatement, RawPosition, RawTransaction


class OSLParser(BrokerParser):
    broker_name = "osl"
    account_currency = "USD"

    def parse(self, text: str, tables: list, filename: str = "") -> ParsedStatement:
        statement = ParsedStatement(
            broker="osl",
            account_name=self._extract_account_name(text),
            statement_date=self._extract_statement_date(text),
            currency="USD",
        )

        # Claude Vision pipe-delimited output
        if "POSITION |" in text or "TRANSACTION |" in text:
            self._parse_vision_output(text, statement)
            return statement

        self._parse_balance_summary(tables, text, statement)
        self._parse_trade_transactions(tables, text, statement)

        return statement

    # ── Section 1A: Account Balance Summary ──────────────────────────────────

    def _parse_balance_summary(self, tables: list, text: str, stmt: ParsedStatement) -> None:
        """
        Extract month-end holdings from Account Balance Summary table.
        Columns: Currency | Opening Balance | Net Movement | Closing Balance |
                 Closing Market Price/Exchange Rate | Market Value (USD)
        """
        for table in tables:
            if not table or len(table) < 2:
                continue

            header = [str(c).strip().lower() if c else "" for c in table[0]]
            full_header = " ".join(header)

            is_balance = (
                "closing account balance" in full_header
                or ("currency" in full_header and "net movement" in full_header)
            )
            if not is_balance:
                continue

            col = {}
            for i, h in enumerate(header):
                if h in ("currency(2)(4)", "currency") or h.startswith("currency"):
                    col["symbol"] = i
                elif "closing account balance" in h or (h == "closing" and "balance" in full_header):
                    col["qty"] = i
                elif "closing market" in h or "price/exchange" in h or "exchange rate" in h:
                    col["price"] = i
                elif "market value" in h:
                    col["value"] = i

            # Fallback column positions if header detection is off
            if "symbol" not in col:
                col["symbol"] = 0
            if "qty" not in col:
                col["qty"] = 3   # Closing Account Balance is 4th column
            if "price" not in col:
                col["price"] = 4
            if "value" not in col:
                col["value"] = 5

            for row in table[1:]:
                if not row:
                    continue

                symbol = str(row[col["symbol"]]).strip().upper() if col["symbol"] < len(row) else ""
                if not symbol or symbol.lower() in ("currency", "total", ""):
                    continue

                # Skip "Total" row
                if symbol.lower() == "total":
                    continue

                qty_raw = row[col["qty"]] if col["qty"] < len(row) else None
                qty = self._safe_decimal(qty_raw)

                # Skip zero balances (e.g. HKD that was fully withdrawn)
                if qty == Decimal("0"):
                    continue

                price_raw = row[col["price"]] if col["price"] < len(row) else None
                price_str = str(price_raw).strip() if price_raw else ""
                price = self._safe_decimal(price_str) if price_str.upper() not in ("N/A", "") else None

                value_raw = row[col["value"]] if col["value"] < len(row) else None
                value_str = str(value_raw).strip() if value_raw else ""
                value = self._safe_decimal(value_str) if value_str.upper() not in ("N/A", "") else None

                # HKD/USD cash positions
                if symbol in ("HKD", "USD", "USDT", "USDC"):
                    stmt.positions.append(RawPosition(
                        symbol=f"{symbol}.CASH",
                        name=f"{symbol} Cash",
                        quantity=qty,
                        price=Decimal("1"),
                        currency=symbol if symbol in ("USD", "HKD") else "USD",
                        market_value=value,
                        asset_type_hint="cash",
                    ))
                else:
                    # Crypto — price is in USD
                    stmt.positions.append(RawPosition(
                        symbol=symbol,
                        name=symbol,
                        quantity=qty,
                        price=price,
                        currency="USD",
                        market_value=value,
                        asset_type_hint="crypto",
                    ))

    # ── Section 2B: Trade Transactions ───────────────────────────────────────

    def _parse_trade_transactions(self, tables: list, text: str, stmt: ParsedStatement) -> None:
        """
        Extract buy/sell trades from Trade Transactions table.
        Date format: DD/MM/YYYY HH:MM

        Columns: Date | Tx Type | Trade State | Buy/Sell | Currency |
                 Qty/Amount | Executed Price In Consideration CCY |
                 Consideration CCY | Consideration | Fee | Trade Reference
        """
        for table in tables:
            if not table or len(table) < 2:
                continue

            header = [str(c).strip().lower() if c else "" for c in table[0]]
            full_header = " ".join(header)

            is_trades = (
                "buy/sell" in full_header
                or ("trade" in full_header and "consideration" in full_header)
            )
            if not is_trades:
                continue

            col = {}
            for i, h in enumerate(header):
                if h == "date":
                    col["date"] = i
                elif "buy/sell" in h:
                    col["side"] = i
                elif h.startswith("currency"):
                    col["currency"] = i
                elif "quantity" in h or "qty" in h or "amount" in h:
                    col["qty"] = i
                elif "executed price" in h:
                    col["exec_price"] = i
                elif "consideration currency" in h or h == "consideration\ncurrency":
                    col["consid_ccy"] = i
                elif h == "consideration":
                    col["consideration"] = i
                elif "fee" in h:
                    col["fee"] = i

            # Fallback positions based on known OSL column order
            if "date" not in col:
                col["date"] = 0
            if "side" not in col:
                col["side"] = 3
            if "currency" not in col:
                col["currency"] = 4
            if "qty" not in col:
                col["qty"] = 5
            if "exec_price" not in col:
                col["exec_price"] = 6
            if "consid_ccy" not in col:
                col["consid_ccy"] = 7
            if "consideration" not in col:
                col["consideration"] = 8
            if "fee" not in col:
                col["fee"] = 9

            for row in table[1:]:
                if not row:
                    continue

                date_raw = str(row[col["date"]]).strip() if col["date"] < len(row) else ""
                if not date_raw:
                    continue

                trade_date = self._parse_osl_date(date_raw)
                if not trade_date:
                    continue

                side_raw = str(row[col["side"]]).strip().lower() if col["side"] < len(row) else ""
                tx_type = "buy" if "buy" in side_raw else "sell"

                symbol = str(row[col["currency"]]).strip().upper() if col["currency"] < len(row) else ""
                if not symbol:
                    continue

                qty = self._safe_decimal(row[col["qty"]] if col["qty"] < len(row) else None) or None
                exec_price = self._safe_decimal(row[col["exec_price"]] if col["exec_price"] < len(row) else None) or None
                consid_ccy = str(row[col["consid_ccy"]]).strip().upper() if col["consid_ccy"] < len(row) and row[col["consid_ccy"]] else "HKD"
                consideration = self._safe_decimal(row[col["consideration"]] if col["consideration"] < len(row) else None) or None
                fee = self._safe_decimal(row[col["fee"]] if col["fee"] < len(row) else None)

                stmt.transactions.append(RawTransaction(
                    trade_date=trade_date,
                    tx_type=tx_type,
                    symbol=symbol,
                    quantity=qty,
                    price=exec_price,         # Price is per unit in HKD
                    gross_amount=consideration, # Total paid in HKD
                    fee=fee,
                    currency=consid_ccy,       # HKD
                    notes=f"OSL E-Trade",
                    asset_type_hint="crypto",
                ))

    # ── Claude Vision fallback ────────────────────────────────────────────────

    def _parse_vision_output(self, text: str, stmt: ParsedStatement) -> None:
        for line in text.splitlines():
            parts = [p.strip() for p in line.split("|")]
            if not parts:
                continue
            if parts[0].upper() == "POSITION" and len(parts) >= 7:
                _, symbol, name, qty_s, price_s, ccy, value_s = parts[:7]
                if not symbol:
                    continue
                stmt.positions.append(RawPosition(
                    symbol=symbol.upper(),
                    name=name or symbol,
                    quantity=self._safe_decimal(qty_s),
                    price=self._safe_decimal(price_s) or None,
                    currency=ccy or "USD",
                    market_value=self._safe_decimal(value_s) or None,
                    asset_type_hint="crypto",
                ))
            elif parts[0].upper() == "TRANSACTION" and len(parts) >= 9:
                _, date_s, tx_type, symbol, qty_s, price_s, amount_s, fee_s, ccy = parts[:9]
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
                    currency=ccy or "HKD",
                    asset_type_hint="crypto",
                ))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _parse_osl_date(self, date_str: str):
        """Parse OSL date format: DD/MM/YYYY HH:MM or DD/MM/YYYY"""
        date_str = date_str.strip()
        for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(date_str[:16] if len(date_str) > 10 else date_str, fmt).date()
            except ValueError:
                continue
        return self._safe_date(date_str)

    def _extract_account_name(self, text: str) -> str | None:
        # "Account: sam.s***@mail.com - b8eba8ac-..."
        m = re.search(r"Account:\s*([^\n]+)", text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    def _extract_statement_date(self, text: str):
        # "Monthly Statement of Account - Feb, 2026"
        m = re.search(r"Statement of Account\s*-\s*([\w]+,?\s*\d{4})", text, re.IGNORECASE)
        if m:
            return self._safe_date(f"01 {m.group(1)}")
        # "01 Mar, 2026" at top of statement
        m = re.search(r"(\d{2}\s+\w+,?\s+\d{4})", text)
        return self._safe_date(m.group(1)) if m else None
