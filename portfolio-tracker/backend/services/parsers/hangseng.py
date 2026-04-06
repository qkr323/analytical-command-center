"""
Hang Seng Bank Securities Account Monthly Consolidated Statement parser.

Statement sections:
  Portfolio details:
      SecuritiesID | Securities description
      Opening balance | Closing balance | Market unit price | Market value

  Transaction summary:
      Securities ID | Securities description
      Transaction date / Settlement date | Unit price | Quantity | Settlement amount
      Reference | Type (PUR/SEL)

  Charges and income summary:
      Date | Charges/income description | Charges amount | Income amount

Date format: DDMMMYYYY (e.g. 27MAR2026)
All values in HKD.
"""
from __future__ import annotations

import re
from datetime import datetime, date
from decimal import Decimal

from services.parsers.base import BrokerParser, ParsedStatement, RawPosition, RawTransaction

# Month abbreviation map
_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


class HangSengParser(BrokerParser):
    broker_name = "hangseng"
    account_currency = "HKD"

    def parse(self, text: str, tables: list, filename: str = "") -> ParsedStatement:
        statement = ParsedStatement(
            broker="hangseng",
            account_name=self._extract_account_name(text),
            statement_date=self._extract_statement_date(text),
            currency="HKD",
        )
        self._parse_holdings(text, statement)
        self._parse_transactions(text, statement)
        return statement

    # ── Holdings ──────────────────────────────────────────────────────────────

    def _parse_holdings(self, text: str, stmt: ParsedStatement) -> None:
        """
        Parse portfolio holdings section.
        Pattern per holding:
          <CODE> <NAME>
          <opening_qty> <closing_qty> HKD <unit_price> HKD <market_value>
        """
        # Match blocks like:
        # 02800 TRACKER FUND OF HONG KONG (SHS)
        # 500 500 HKD 25.08000 HKD 12,540.00
        pattern = re.compile(
            r'(\d{4,6})\s+(.+?)\n'            # securities ID + name
            r'[\d,]+\s+([\d,]+)\s+'            # opening qty  closing qty
            r'HKD\s+([\d,\.]+)\s+'            # unit price
            r'HKD\s+([\d,\.]+)',               # market value
            re.MULTILINE,
        )
        for m in pattern.finditer(text):
            symbol = m.group(1).lstrip("0") or m.group(1)  # strip leading zeros
            name = m.group(2).strip()
            qty = self._safe_decimal(m.group(3))
            price = self._safe_decimal(m.group(4))
            value = self._safe_decimal(m.group(5))

            if qty == Decimal("0"):
                continue

            stmt.positions.append(RawPosition(
                symbol=symbol,
                name=name,
                quantity=qty,
                price=price,
                currency="HKD",
                market_value=value,
                asset_type_hint=self._guess_type(name),
            ))

    # ── Transactions ──────────────────────────────────────────────────────────

    def _parse_transactions(self, text: str, stmt: ParsedStatement) -> None:
        """
        Parse transaction summary section.
        Pattern:
          <CODE> <NAME>
          <date> <settle_date> HKD <price> <qty> HKD <amount>
          Reference: ... Type: PUR/SEL
        """
        # Find the transaction summary block
        tx_section_match = re.search(r'Transaction summary(.+?)(?:Charges and income|$)', text, re.DOTALL)
        if not tx_section_match:
            return
        tx_text = tx_section_match.group(1)

        # Match individual transactions
        pattern = re.compile(
            r'(\d{4,6})\s+(.+?)\n'                           # code + name
            r'(\d{2}[A-Z]{3}\d{4})\s+(?:\d{2}[A-Z]{3}\d{4}|TBC)\s+'  # tx date + settle date
            r'HKD\s+([\d,\.]+)\s+'                           # unit price
            r'([\d,]+)\s+'                                    # quantity
            r'HKD\s+([\d,\.]+)\n'                            # settlement amount
            r'Reference:\s*\S+\s+Type:\s*(PUR|SEL)',         # reference + type
            re.MULTILINE,
        )
        for m in pattern.finditer(tx_text):
            symbol = m.group(1).lstrip("0") or m.group(1)
            name = m.group(2).strip()
            tx_date = self._parse_hs_date(m.group(3))
            price = self._safe_decimal(m.group(4))
            qty = self._safe_decimal(m.group(5))
            amount = self._safe_decimal(m.group(6))
            tx_type = "buy" if m.group(7) == "PUR" else "sell"

            if not tx_date or qty == Decimal("0"):
                continue

            stmt.transactions.append(RawTransaction(
                trade_date=tx_date,
                tx_type=tx_type,
                symbol=symbol,
                quantity=qty,
                price=price,
                gross_amount=amount,
                fee=Decimal("0"),
                currency="HKD",
                notes="Hang Seng Securities",
                asset_type_hint=self._guess_type(name),
            ))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _parse_hs_date(self, date_str: str) -> date | None:
        """Parse DDMMMYYYY format, e.g. 27MAR2026."""
        date_str = date_str.strip().upper()
        m = re.match(r'(\d{2})([A-Z]{3})(\d{4})', date_str)
        if not m:
            return None
        day, mon, year = int(m.group(1)), _MONTHS.get(m.group(2)), int(m.group(3))
        if not mon:
            return None
        try:
            return date(year, mon, day)
        except ValueError:
            return None

    def _extract_account_name(self, text: str) -> str | None:
        m = re.search(r'A/C name\s*:(.+)', text)
        return m.group(1).strip() if m else None

    def _extract_statement_date(self, text: str) -> date | None:
        m = re.search(r'Date\s*:(\d{2}[A-Z]{3}\d{4})', text)
        return self._parse_hs_date(m.group(1)) if m else None

    def _guess_type(self, name: str) -> str:
        desc = name.lower()
        etf_kw = ("tracker fund", "etf", "fund", "index", "ishares", "xtrackers",
                  "agx", "hscei", "csi", "ftse")
        if any(kw in desc for kw in etf_kw):
            return "etf"
        return "stock"
