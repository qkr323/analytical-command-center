"""
SoFi Hong Kong (SoFi Securities (Hong Kong) Limited) statement parser.

pdfplumber extracts no tables — all parsing is text-based via regex.

Text structure (from actual statement):
  Cash section:
    HKD 31,881.92 0.00 31,881.92 85,100.00
    USD 6,198.17  0.00  6,198.17  9,073.70

  Stock/Product Position section:
    HK - HK Market (HKD)
    00384 CHINA GAS HOLD 800 0 800 7.150 5,720.00 50 2,860.00
    01508 CHINA RE 54,000 0 54,000 1.470 79,380.00 0 0.00
    US - US Market (USD)
    VGSH VANGUARD SCOTTSDALE FDS- 155 0 155 58.540 9,073.70 0 0.00

  Account Movement section:
    0004990295 2026-03-05 Deposit Dividend/Cash VGSH:US ... USD 26.29 6,206.06
    0004640632 2026-03-05 Withdraw Dividend tax VGSH:US ... USD (7.89) 6,198.17
"""
from __future__ import annotations

import re
from decimal import Decimal

from services.parsers.base import BrokerParser, ParsedStatement, RawPosition, RawTransaction


class SoFiParser(BrokerParser):
    broker_name = "sofi"
    account_currency = "HKD"

    def parse(self, text: str, tables: list, filename: str = "") -> ParsedStatement:
        statement = ParsedStatement(
            broker="sofi",
            account_name=self._extract_account_name(text),
            statement_date=self._extract_statement_date(text),
            currency="HKD",
        )

        # Claude Vision pipe-delimited fallback
        if "POSITION |" in text or "TRANSACTION |" in text:
            self._parse_vision_output(text, statement)
            return statement

        self._parse_cash_balances(text, statement)
        self._parse_stock_positions(text, statement)
        self._parse_account_movements(text, statement)

        return statement

    # ── Cash balances ─────────────────────────────────────────────────────────

    def _parse_cash_balances(self, text: str, stmt: ParsedStatement) -> None:
        """
        Pattern: HKD 31,881.92 0.00 31,881.92 85,100.00
                 USD  6,198.17 0.00  6,198.17  9,073.70
        Column order: CCY | Today Balance | Pending Settlement | Net Balance | Stock Holdings Total
        We want Net Balance (column 4).
        """
        pattern = re.compile(
            r"^(HKD|USD)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})",
            re.MULTILINE,
        )
        for m in pattern.finditer(text):
            ccy = m.group(1)
            net = self._safe_decimal(m.group(4))
            if net > 0:
                stmt.positions.append(RawPosition(
                    symbol=f"{ccy}.CASH",
                    name=f"{ccy} Cash",
                    quantity=net,
                    price=Decimal("1"),
                    currency=ccy,
                    market_value=net,
                    asset_type_hint="cash",
                ))

    # ── Stock positions ───────────────────────────────────────────────────────

    def _parse_stock_positions(self, text: str, stmt: ParsedStatement) -> None:
        """
        Extract the Stock/Product Position section and parse each holding.

        HK stocks: 5-digit numeric code
          00384 CHINA GAS HOLD 800 0 800 7.150 5,720.00 50 2,860.00

        US stocks: alpha ticker (up to 5 chars)
          VGSH VANGUARD SCOTTSDALE FDS- 155 0 155 58.540 9,073.70 0 0.00
          (name may wrap to next line)
        """
        # Isolate section between "Stock/Product Position" and "Dividend"
        section_match = re.search(
            r"Stock/Product Position(.+?)(?:Dividend|Margin Loan|End of Statement)",
            text,
            re.DOTALL | re.IGNORECASE,
        )
        if not section_match:
            stmt.parse_warnings.append("SoFi: Could not find Stock/Product Position section")
            return

        section = section_match.group(1)
        current_currency = "HKD"

        lines = section.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Track which market we're in
            if "HK - HK Market" in line or "HK MARKET" in line.upper():
                current_currency = "HKD"
                i += 1
                continue
            if "US - US Market" in line or "US MARKET" in line.upper():
                current_currency = "USD"
                i += 1
                continue

            # Skip subtotal lines e.g. "HKD 85,100.00 2,860.00"
            if re.match(r"^(HKD|USD)\s+[\d,]+\.\d{2}", line):
                i += 1
                continue

            # HK stock: starts with 5-digit code
            # e.g. "00384 CHINA GAS HOLD 800 0 800 7.150 5,720.00 50 2,860.00"
            hk_match = re.match(
                r"^(\d{4,5})\s+(.+?)\s+([\d,]+)\s+\d+\s+([\d,]+)\s+([\d.]+)\s+([\d,]+\.\d{2})",
                line,
            )
            if hk_match:
                symbol = hk_match.group(1)
                name = hk_match.group(2).strip()
                qty = self._safe_decimal(hk_match.group(4))   # Net Balance
                price = self._safe_decimal(hk_match.group(5))
                value = self._safe_decimal(hk_match.group(6))
                stmt.positions.append(RawPosition(
                    symbol=symbol,
                    name=name,
                    quantity=qty,
                    price=price,
                    currency="HKD",
                    market_value=value,
                    asset_type_hint="stock",
                ))
                i += 1
                continue

            # US stock: starts with 1-5 alpha chars
            # e.g. "VGSH VANGUARD SCOTTSDALE FDS- 155 0 155 58.540 9,073.70 0 0.00"
            us_match = re.match(
                r"^([A-Z]{1,5})\s+(.+?)\s+([\d,]+)\s+\d+\s+([\d,]+)\s+([\d.]+)\s+([\d,]+\.\d{2})",
                line,
            )
            if us_match:
                symbol = us_match.group(1)
                name = us_match.group(2).strip()

                # Handle wrapped name on next line (e.g. "SHORT TERM TREAS")
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and not re.match(r"^[\d]", next_line) and not re.match(r"^[A-Z]{1,5}\s+\d", next_line):
                        # Check it's not a market header or subtotal
                        if not any(kw in next_line.upper() for kw in ("HK -", "US -", "HKD ", "USD ")):
                            name = f"{name} {next_line}"
                            i += 1

                qty = self._safe_decimal(us_match.group(4))   # Net Balance
                price = self._safe_decimal(us_match.group(5))
                value = self._safe_decimal(us_match.group(6))

                stmt.positions.append(RawPosition(
                    symbol=symbol,
                    name=name.strip(),
                    quantity=qty,
                    price=price,
                    currency="USD",
                    market_value=value,
                    asset_type_hint=self._guess_asset_type(symbol, name),
                ))
                i += 1
                continue

            i += 1

    # ── Account movements ─────────────────────────────────────────────────────

    def _parse_account_movements(self, text: str, stmt: ParsedStatement) -> None:
        """
        Pattern with reference number:
          0004990295 2026-03-05 Deposit Dividend/Cash VGSH:US ... USD 26.29 6,206.06

        Pattern without reference number (B/F line — skip):
          2026-03-30 B/F USD 6,179.77

        Amount may be negative with parentheses: (7.89)
        """
        section_match = re.search(
            r"Account Movement(.+?)Stock/Product Position",
            text,
            re.DOTALL | re.IGNORECASE,
        )
        if not section_match:
            return

        section = section_match.group(1)

        # Detect movement currency block (USD or HKD)
        movement_currency = "USD"

        tx_pattern = re.compile(
            r"(\d{10})\s+"                          # Reference number (10 digits)
            r"(\d{4}-\d{2}-\d{2})\s+"              # Transaction date
            r"(\w+)\s+"                              # Type: Deposit / Withdraw
            r"(.+?)\s+"                              # Description
            r"(USD|HKD)\s+"                          # Currency
            r"(\([\d.]+\)|[\d,]+\.\d{2})\s+",      # Amount (may be in parens)
            re.MULTILINE,
        )

        for m in tx_pattern.finditer(section):
            trade_date = self._safe_date(m.group(2))
            if not trade_date:
                continue

            tx_type_raw = m.group(3).lower()
            desc = m.group(4).strip()
            ccy = m.group(5)
            amount_raw = m.group(6)

            # Parse amount — parentheses = negative
            is_negative = "(" in amount_raw
            amount = self._safe_decimal(amount_raw.replace("(", "").replace(")", ""))
            if is_negative:
                amount = -amount

            # Extract symbol from description (e.g. "VGSH:US" → "VGSH")
            sym_match = re.match(r"([A-Z0-9]{1,6})(?::US|:HK)?", desc.upper())
            symbol = sym_match.group(1) if sym_match else None

            tx_type = self._classify_movement(tx_type_raw, desc)

            stmt.transactions.append(RawTransaction(
                trade_date=trade_date,
                tx_type=tx_type,
                symbol=symbol,
                quantity=None,
                price=None,
                gross_amount=abs(amount),
                fee=Decimal("0"),
                currency=ccy,
                notes=desc,
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
                    symbol=symbol,
                    name=name or None,
                    quantity=self._safe_decimal(qty_s),
                    price=self._safe_decimal(price_s) or None,
                    currency=ccy or "HKD",
                    market_value=self._safe_decimal(value_s) or None,
                    asset_type_hint=self._guess_asset_type(symbol, name),
                ))
            elif parts[0].upper() == "TRANSACTION" and len(parts) >= 9:
                _, date_s, tx_type, symbol, qty_s, price_s, amount_s, fee_s, ccy = parts[:9]
                trade_date = self._safe_date(date_s)
                if not trade_date:
                    continue
                stmt.transactions.append(RawTransaction(
                    trade_date=trade_date,
                    tx_type=tx_type.lower() or "buy",
                    symbol=symbol or None,
                    quantity=self._safe_decimal(qty_s) or None,
                    price=self._safe_decimal(price_s) or None,
                    gross_amount=self._safe_decimal(amount_s) or None,
                    fee=self._safe_decimal(fee_s),
                    currency=ccy or "HKD",
                ))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _classify_movement(self, tx_type_raw: str, desc: str) -> str:
        desc_lower = desc.lower()
        if "dividend" in desc_lower and "tax" not in desc_lower:
            return "dividend"
        if "tax" in desc_lower or "withholding" in desc_lower:
            return "fee"
        if "deposit" in tx_type_raw:
            return "deposit"
        if "withdraw" in tx_type_raw:
            return "withdrawal"
        if "buy" in desc_lower:
            return "buy"
        if "sell" in desc_lower:
            return "sell"
        return "fee"

    def _extract_account_name(self, text: str) -> str | None:
        m = re.search(r"Client A/C[:\s]+([A-Z0-9\-]+)", text, re.IGNORECASE)
        return m.group(1) if m else None

    def _extract_statement_date(self, text: str):
        m = re.search(r"Date[:\s]+(\d{4}-\d{2}-\d{2})", text, re.IGNORECASE)
        return self._safe_date(m.group(1)) if m else None

    def _guess_asset_type(self, symbol: str, name: str | None) -> str:
        sym = (symbol or "").upper().strip()
        desc = (name or "").lower()
        if sym in ("HKD.CASH", "USD.CASH"):
            return "cash"
        if re.match(r"^\d{4,5}$", sym):
            return "stock"
        if sym in ("BTC", "ETH", "SOL", "XRP", "ADA", "DOGE", "AVAX"):
            return "crypto"
        if any(kw in desc for kw in ("etf", "fund", "index", "trust", "treas", "scottsdale")):
            return "etf"
        return "stock"
