"""
Portfolio summary endpoints.
Returns aggregated positions across all accounts, valued in HKD.
"""
from decimal import Decimal
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from database import get_db
from models.account import Account
from models.asset import AssetTypeEnum
from models.position import Position

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


class PositionOut(BaseModel):
    id: int
    account_id: int
    account_name: str
    broker: str
    symbol: str
    asset_name: str | None
    asset_type: str
    quantity: Decimal
    avg_cost_hkd: Decimal | None
    last_price_hkd: Decimal | None
    market_value_hkd: Decimal | None
    unrealized_pnl_hkd: Decimal | None
    unrealized_pnl_pct: Decimal | None
    currency: str
    compliance_status: str

    model_config = {"from_attributes": True}


class PortfolioSummary(BaseModel):
    total_nav_hkd: Decimal
    total_cost_hkd: Decimal
    total_unrealized_pnl_hkd: Decimal
    total_unrealized_pnl_pct: Decimal | None
    by_asset_type: dict[str, Decimal]
    by_broker: dict[str, Decimal]
    positions: list[PositionOut]


@router.get("/summary", response_model=PortfolioSummary)
async def get_portfolio_summary(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Position)
        .options(
            selectinload(Position.account),
            selectinload(Position.asset),
        )
        .where(Position.quantity > 0)
        .order_by(Position.market_value_hkd.desc().nulls_last())
    )
    positions = result.scalars().all()

    total_nav = Decimal("0")
    total_cost = Decimal("0")
    by_type: dict[str, Decimal] = {}
    by_broker: dict[str, Decimal] = {}
    position_outs = []

    for pos in positions:
        nav = pos.market_value_hkd or Decimal("0")
        cost = pos.total_cost_hkd or Decimal("0")
        pnl = pos.unrealized_pnl_hkd

        # Recalculate P&L if not already set
        if pnl is None and pos.market_value_hkd and pos.total_cost_hkd:
            pnl = pos.market_value_hkd - pos.total_cost_hkd

        total_nav += nav
        total_cost += cost

        asset_type = pos.asset.asset_type.value if pos.asset else "unknown"
        broker = pos.account.broker.value if pos.account else "unknown"

        by_type[asset_type] = by_type.get(asset_type, Decimal("0")) + nav
        by_broker[broker] = by_broker.get(broker, Decimal("0")) + nav

        position_outs.append(PositionOut(
            id=pos.id,
            account_id=pos.account_id,
            account_name=pos.account.name if pos.account else "",
            broker=broker,
            symbol=pos.asset.symbol if pos.asset else "",
            asset_name=pos.asset.name if pos.asset else None,
            asset_type=asset_type,
            quantity=pos.quantity,
            avg_cost_hkd=pos.avg_cost_hkd,
            last_price_hkd=pos.last_price_hkd,
            market_value_hkd=pos.market_value_hkd,
            unrealized_pnl_hkd=pnl,
            unrealized_pnl_pct=pos.unrealized_pnl_pct,
            currency=pos.cost_currency,
            compliance_status=pos.asset.compliance_status.value if pos.asset else "unknown",
        ))

    total_pnl = total_nav - total_cost
    pnl_pct = (total_pnl / total_cost * 100) if total_cost else None

    return PortfolioSummary(
        total_nav_hkd=total_nav,
        total_cost_hkd=total_cost,
        total_unrealized_pnl_hkd=total_pnl,
        total_unrealized_pnl_pct=pnl_pct,
        by_asset_type=by_type,
        by_broker=by_broker,
        positions=position_outs,
    )


@router.get("/positions", response_model=list[PositionOut])
async def list_positions(
    broker: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Position)
        .options(selectinload(Position.account), selectinload(Position.asset))
        .where(Position.quantity > 0)
        .order_by(Position.market_value_hkd.desc().nulls_last())
    )
    if broker:
        query = query.join(Account).where(Account.broker == broker)

    result = await db.execute(query)
    positions = result.scalars().all()

    return [
        PositionOut(
            id=p.id,
            account_id=p.account_id,
            account_name=p.account.name if p.account else "",
            broker=p.account.broker.value if p.account else "",
            symbol=p.asset.symbol if p.asset else "",
            asset_name=p.asset.name if p.asset else None,
            asset_type=p.asset.asset_type.value if p.asset else "unknown",
            quantity=p.quantity,
            avg_cost_hkd=p.avg_cost_hkd,
            last_price_hkd=p.last_price_hkd,
            market_value_hkd=p.market_value_hkd,
            unrealized_pnl_hkd=p.unrealized_pnl_hkd,
            unrealized_pnl_pct=p.unrealized_pnl_pct,
            currency=p.cost_currency,
            compliance_status=p.asset.compliance_status.value if p.asset else "unknown",
        )
        for p in positions
    ]
