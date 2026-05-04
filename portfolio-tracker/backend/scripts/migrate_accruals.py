"""
Migration: create interest_accruals and dividend_accruals tables.

Safe to run multiple times — uses create_all() which skips existing tables.
Run via:
    cd backend
    source ../.venv/bin/activate
    python -m scripts.migrate_accruals
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import engine, Base
from models import InterestAccrual, DividendAccrual


async def run():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✓ Created interest_accruals table")
    print("✓ Created dividend_accruals table")
    print("Migration complete.")


if __name__ == "__main__":
    asyncio.run(run())
