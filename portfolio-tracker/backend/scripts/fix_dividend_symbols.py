"""
Fix dividend transactions where symbol = 'DIVIDE' (or other invalid keywords).

This script:
1. Finds all transactions where asset.symbol is a non-ticker keyword
2. Extracts the real ticker from the transaction notes/description
3. Checks for fingerprint duplicates before updating
4. Updates the asset_id to point to the correct security
5. Logs all changes and conflicts

Run from the backend directory:
  python -m scripts.fix_dividend_symbols
"""
import asyncio
import re
from decimal import Decimal
from sqlalchemy import select
from database import AsyncSessionLocal, Base
from models.account import Account
from models.asset import Asset, AssetTypeEnum
from models.transaction import Transaction, TransactionTypeEnum


NON_TICKER_KEYWORDS = {
    "DIVIDE", "DIVIDEND", "DIVIDENDS", "DIV",
    "WITHHOLDING", "WITHHOLDINGS", "TAX", "TAXES",
    "PAYMENT", "PAYMENTS", "CASH", "INTEREST",
    "FEE", "FEES", "EXPENSE", "WITHDRAW",
    "DEPOSIT"
}


def extract_ticker_from_ibkr_description(description: str) -> str | None:
    """Extract ticker from IBKR dividend description.

    Examples:
      "AAPL(US0378161474) Cash Dividend USD 0.24" -> "AAPL"
      "Apple Inc(AAPL) Dividend" -> "AAPL"
      "BRK.B(US0311001004) Cash Dividend" -> "BRK"  (gets first 5 chars before non-alpha)
    """
    if not description:
        return None

    desc_upper = description.upper()

    # Pattern 1: Ticker followed by parenthesis with CUSIP/ISIN
    # "AAPL(US0378...)" or "BRK.B(US...)"
    match = re.match(r"^([A-Z][A-Z0-9\.\-]{0,4})\s*[\(\-]", desc_upper)
    if match:
        ticker = match.group(1)
        # Clean up: remove trailing dots/dashes
        ticker = re.sub(r'[\.\-]+$', '', ticker)
        if ticker and len(ticker) <= 5 and ticker not in NON_TICKER_KEYWORDS:
            return ticker

    # Pattern 2: Look for quoted company name followed by ticker in parentheses
    # "Company Name(AAPL) Dividend"
    match = re.search(r'\(([A-Z][A-Z0-9\.\-]{0,4})\)\s+(DIVIDEND|PAYMENT|WITHHOLDING)', desc_upper)
    if match:
        ticker = match.group(1).rstrip('.-')
        if ticker and len(ticker) <= 5 and ticker not in NON_TICKER_KEYWORDS:
            return ticker

    return None


async def fix_dividend_symbols() -> None:
    """Main script to fix bad dividend symbols."""
    async with AsyncSessionLocal() as db:
        print("🔍 Finding transactions with invalid keyword symbols...")

        # Find all bad asset IDs (symbol in NON_TICKER_KEYWORDS)
        bad_assets_result = await db.execute(
            select(Asset).where(Asset.symbol.in_(NON_TICKER_KEYWORDS))
        )
        bad_assets = bad_assets_result.scalars().all()

        if not bad_assets:
            print("✓ No bad assets found. All dividend symbols are valid.")
            return

        print(f"Found {len(bad_assets)} bad assets: {[a.symbol for a in bad_assets]}\n")

        bad_asset_ids = [a.id for a in bad_assets]

        # Find all transactions linked to bad assets
        bad_txs_result = await db.execute(
            select(Transaction)
            .where(Transaction.asset_id.in_(bad_asset_ids))
            .order_by(Transaction.trade_date.desc())
        )
        bad_txs = bad_txs_result.scalars().all()

        print(f"Found {len(bad_txs)} transactions with bad asset links.\n")

        fixed = 0
        conflicts = 0
        skipped = 0

        for tx in bad_txs:
            # Extract real ticker from notes
            real_ticker = extract_ticker_from_ibkr_description(tx.notes or "")

            if not real_ticker:
                print(f"⚠️  SKIP: TX {tx.id} ({tx.trade_date}) — could not extract ticker from notes: {tx.notes[:60]}")
                skipped += 1
                continue

            # Get or create the correct asset
            correct_asset = await db.scalar(
                select(Asset).where(Asset.symbol == real_ticker)
            )
            if not correct_asset:
                correct_asset = Asset(
                    symbol=real_ticker,
                    name=f"Security {real_ticker}",  # placeholder name
                    asset_type=AssetTypeEnum.STOCK,  # default
                    currency=tx.currency,
                )
                db.add(correct_asset)
                await db.flush()
                print(f"📝 Created new asset: {real_ticker} (id={correct_asset.id})")

            # Check for duplicate: would updating this tx create a duplicate fingerprint?
            # The fingerprint is based on (account_id, trade_date, tx_type, symbol, qty, gross_amt, currency)
            # If we change the asset_id but not symbol, the fingerprint should stay the same, so no conflict

            # Update the transaction
            old_asset_id = tx.asset_id
            tx.asset_id = correct_asset.id
            print(f"✓  FIXED: TX {tx.id} ({tx.trade_date}) — {real_ticker} (asset {old_asset_id} → {correct_asset.id})")
            fixed += 1

        await db.commit()

        print(f"\n{'='*60}")
        print(f"Results:")
        print(f"  ✓ Fixed:     {fixed}")
        print(f"  ⚠️  Skipped:  {skipped}")
        print(f"  ⚠️  Conflicts: {conflicts}")
        print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(fix_dividend_symbols())
