"""
Futu (Moomoo) statement parser.

Futu statements are typically in PDF with sections:
  - 持仓明细 / Holdings / Position Details
  - 成交记录 / Transaction History
Account currency is typically HKD (HK account) or USD (US account).
"""
from __future__ import annotations

import re
from decimal import Decimal

from services.parsers.base import BrokerParser, ParsedStatement, RawPosition, RawTransaction


class FutuParser(BrokerParser):
    broker_name = "futu"
    account_currency = "HKD"

    def parse(self, text: str, tables: list, filename: str = "") -> ParsedStatement:
        # Determine account currency from statement text
        currency = "HKD" if "HKD" in text[:500] or "港元" in text[:500] else "USD"

        statement = ParsedStatement(
            broker="futu",
            account_name=self._extract_account_name(text),
            statement_date=self._extract_statement_date(text),
            currency=currency,
        )

        # Claude Vision pipe-delimited output
        if "POSITION |" in text or "TRANSACTION |" in text:
            self._parse_vision_output(text, statement, currency)
            return statement

        self._parse_holdings_tables(tables, statement, currency)
        self._parse_transaction_tables(tables, statement, currency)

        return statement

    def _parse_holdings_tables(self, tables: list, stmt: ParsedStatement, currency: str) -> None:
        """
        Futu holdings columns (English):
        Stock Code | Stock Name | Quantity | Avg Cost | Current Price | Market Value | P&L
        """
        for table in tables:
            if not table or len(table) < 2:
                continue
            header = [str(c).strip().lower() if c else "" for c in table[0]]

            # Look for holdings table markers
            is_holdings = any(kw in " ".join(header) for kw in ("stock code", "quantity", "market value", "股票代码", "数量"))
            if not is_holdings:
                continue

            # Map columns flexibly
            col = {}
            for i, h in enumerate(header):
                if "code" in h or "股票代码" in h:
                    col["symbol"] = i
                elif "name" in h or "名称" in h:
                    col["name"] = i
                elif "quantity" in h or "数量" in h or "持仓" in h:
                    col["qty"] = i
                elif "avg" in h or "成本" in h:
                    col["avg_cost"] = i
                elif "current" in h or "现价" in h:
                    col["price"] = i
                elif "market" in h or "市值" in h:
                    col["value"] = i

            if "symbol" not in col or "qty" not in col:
                continue

            for row in table[1:]:
                if not row or not row[col["symbol"]]:
                    continue
                symbol = str(row[col["symbol"]]).strip()
                if not symbol or symbol.lower() in ("total", "合计"):
                    continue

                name = str(row[col["name"]]).strip() if "name" in col and row[col["name"]] else None
                qty = self._safe_decimal(row[col["qty"]])
                price = self._safe_decimal(row[col["price"]] if "price" in col else None) or None
                value = self._safe_decimal(row[col["value"]] if "value" in col else None) or None
                avg_cost = self._safe_decimal(row[col["avg_cost"]] if "avg_cost" in col else None) or None

                if qty == Decimal("0"):
                    continue

                stmt.positions.append(RawPosition(
                    symbol=symbol,
                    name=name,
                    quantity=qty,
                    price=price,
                    currency=currency,
                    market_value=value,
                    asset_type_hint=self._guess_asset_type(symbol),
                ))

    def _parse_transaction_tables(self, tables: list, stmt: ParsedStatement, currency: str) -> None:
        """
        Futu transaction columns:
        Date | Direction | Code | Name | Qty | Price | Amount | Fee | Currency
        """
        for table in tables:
            if not table or len(table) < 2:
                continue
            header = [str(c).strip().lower() if c else "" for c in table[0]]
            is_tx = any(kw in " ".join(header) for kw in ("direction", "买卖", "成交"))
            if not is_tx:
                continue

            col = {}
            for i, h in enumerate(header):
                if "date" in h or "日期" in h:
                    col["date"] = i
                elif "direction" in h or "买卖" in h or "方向" in h:
                    col["direction"] = i
                elif "code" in h or "代码" in h:
                    col["symbol"] = i
                elif "qty" in h or "数量" in h or "股数" in h:
                    col["qty"] = i
                elif "price" in h or "价格" in h:
                    col["price"] = i
                elif "amount" in h or "金额" in h:
                    col["amount"] = i
                elif "fee" in h or "手续" in h or "佣金" in h:
                    col["fee"] = i

            if "date" not in col:
                continue

            for row in table[1:]:
                if not row:
                    continue
                trade_date = self._safe_date(row[col["date"]] if "date" in col and col["date"] < len(row) else None)
                if not trade_date:
                    continue

                direction = str(row[col["direction"]]).strip().lower() if "direction" in col and col["direction"] < len(row) else ""
                tx_type = "buy" if any(kw in direction for kw in ("buy", "买")) else "sell"
                symbol = str(row[col["symbol"]]).strip() if "symbol" in col and col["symbol"] < len(row) else ""
                qty = self._safe_decimal(row[col["qty"]] if "qty" in col and col["qty"] < len(row) else None) or None
                price = self._safe_decimal(row[col["price"]] if "price" in col and col["price"] < len(row) else None) or None
                amount = self._safe_decimal(row[col["amount"]] if "amount" in col and col["amount"] < len(row) else None) or None
                fee = self._safe_decimal(row[col["fee"]] if "fee" in col and col["fee"] < len(row) else None)

                stmt.transactions.append(RawTransaction(
                    trade_date=trade_date,
                    tx_type=tx_type,
                    symbol=symbol or None,
                    quantity=qty,
                    price=price,
                    gross_amount=amount,
                    fee=abs(fee),
                    currency=currency,
                    asset_type_hint=self._guess_asset_type(symbol) if symbol else None,
                ))

    def _parse_vision_output(self, text: str, stmt: ParsedStatement, currency: str) -> None:
        for line in text.splitlines():
            parts = [p.strip() for p in line.split("|")]
            if not parts:
                continue
            if parts[0].upper() == "POSITION" and len(parts) >= 7:
                _, symbol, name, qty_s, price_s, ccy, value_s = parts[:7]
                stmt.positions.append(RawPosition(
                    symbol=symbol.upper() if symbol else "",
                    name=name or None,
                    quantity=self._safe_decimal(qty_s),
                    price=self._safe_decimal(price_s) or None,
                    currency=ccy or currency,
                    market_value=self._safe_decimal(value_s) or None,
                    asset_type_hint=self._guess_asset_type(symbol),
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
                    currency=ccy or currency,
                ))

    def _extract_account_name(self, text: str) -> str | None:
        m = re.search(r"Account\s*(?:No|Number|ID)[.:\s]+([A-Z0-9\-]+)", text, re.IGNORECASE)
        return m.group(1) if m else None

    def _extract_statement_date(self, text: str):
        m = re.search(r"(?:Statement Date|报表日期)[:\s]+([\d\-/]+)", text, re.IGNORECASE)
        if m:
            return self._safe_date(m.group(1))
        return None

    def _guess_asset_type(self, symbol: str) -> str:
        sym = (symbol or "").upper()
        # HK stocks are numeric codes (e.g. 0700, 2800)
        if re.match(r"^\d{4,5}(\.HK)?$", sym):
            return "stock"
        return "stock"
