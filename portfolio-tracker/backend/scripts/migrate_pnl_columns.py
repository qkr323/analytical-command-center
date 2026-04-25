"""
Migration: add realized P&L columns to the transactions table.

Safe to run multiple times — uses ADD COLUMN IF NOT EXISTS.
Run via:
    cd backend
    source ../.venv/bin/activate
    python -m scripts.migrate_pnl_columns
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import engine


_COLUMNS = [
    ("realized_pnl_local",       "NUMERIC(28,10)"),
    ("realized_pnl_hkd",         "NUMERIC(28,10)"),
    ("cost_basis_local",          "NUMERIC(28,10)"),
    ("cost_basis_hkd",            "NUMERIC(28,10)"),
    ("avg_cost_per_unit_local",   "NUMERIC(28,10)"),
    ("avg_cost_per_unit_hkd",     "NUMERIC(28,10)"),
    ("cost_basis_method",         "VARCHAR(50)"),
    ("calculation_version",       "VARCHAR(20)"),
    ("data_quality_flag",         "VARCHAR(50)"),
    ("pnl_calculated_at",         "TIMESTAMP"),
    ("exclude_from_pnl_totals",   "BOOLEAN DEFAULT FALSE"),
]


async def run():
    async with engine.begin() as conn:
        for col, col_type in _COLUMNS:
            sql = f"ALTER TABLE transactions ADD COLUMN IF NOT EXISTS {col} {col_type}"
            await conn.execute(__import__("sqlalchemy").text(sql))
            print(f"  ✓ {col}")
    print("Migration complete.")


if __name__ == "__main__":
    asyncio.run(run())
