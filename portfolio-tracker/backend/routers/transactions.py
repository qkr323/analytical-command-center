"""
Transaction history endpoints.
GET /transactions — list all transactions with optional filters
"""
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from database import get_db
from models.account import Account
from models.asset import Asset
from models.transaction import Transaction, TransactionTypeEnum

router = APIRouter(prefix="/transactions", tags=["transactions"])


class TransactionOut(BaseModel):
    id: int
    account_id: int
    broker: str
    account_name: str
    symbol: str | None
    asset_name: str | None
    asset_type: str | None
    tx_type: str
    trade_date: date
    quantity: Decimal | None
    price: Decimal | None
    gross_amount: Decimal | None
    fee: Decimal
    net_amount: Decimal | None
    currency: str
    gross_amount_hkd: Decimal | None
    fee_hkd: Decimal | None
    net_amount_hkd: Decimal | None
    notes: str | None

    model_config = {"from_attributes": True}


@router.get("", response_model=list[TransactionOut])
async def list_transactions(
    broker: Optional[str] = Query(None, description="Filter by broker name (e.g. ibkr, futu)"),
    account_id: Optional[int] = Query(None, description="Filter by account ID"),
    symbol: Optional[str] = Query(None, description="Filter by ticker symbol (partial match)"),
    currency: Optional[str] = Query(None, description="Filter by transaction currency (e.g. USD, HKD)"),
    tx_type: Optional[str] = Query(None, description="Filter by type: buy, sell, dividend, fee, deposit, withdrawal"),
    date_from: Optional[date] = Query(None, description="Start date (inclusive), YYYY-MM-DD"),
    date_to: Optional[date] = Query(None, description="End date (inclusive), YYYY-MM-DD"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[TransactionOut]:
    query = (
        select(Transaction)
        .options(
            selectinload(Transaction.account),
            selectinload(Transaction.asset),
        )
        .order_by(Transaction.trade_date.desc(), Transaction.id.desc())
    )

    if account_id is not None:
        query = query.where(Transaction.account_id == account_id)
    elif broker:
        query = query.join(Account, Transaction.account_id == Account.id).where(
            Account.broker == broker
        )

    if symbol:
        query = query.join(Asset, Transaction.asset_id == Asset.id).where(
            Asset.symbol.ilike(f"%{symbol}%")
        )

    if currency:
        query = query.where(Transaction.currency == currency.upper())

    if tx_type:
        try:
            query = query.where(Transaction.tx_type == TransactionTypeEnum(tx_type.lower()))
        except ValueError:
            pass

    if date_from:
        query = query.where(Transaction.trade_date >= date_from)

    if date_to:
        query = query.where(Transaction.trade_date <= date_to)

    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    txs = result.scalars().all()

    return [
        TransactionOut(
            id=tx.id,
            account_id=tx.account_id,
            broker=tx.account.broker.value if tx.account else "unknown",
            account_name=tx.account.name if tx.account else "",
            symbol=tx.asset.symbol if tx.asset else None,
            asset_name=tx.asset.name if tx.asset else None,
            asset_type=tx.asset.asset_type.value if tx.asset else None,
            tx_type=tx.tx_type.value,
            trade_date=tx.trade_date,
            quantity=tx.quantity,
            price=tx.price,
            gross_amount=tx.gross_amount,
            fee=tx.fee,
            net_amount=tx.net_amount,
            currency=tx.currency,
            gross_amount_hkd=tx.gross_amount_hkd,
            fee_hkd=tx.fee_hkd,
            net_amount_hkd=tx.net_amount_hkd,
            notes=tx.notes,
        )
        for tx in txs
    ]
