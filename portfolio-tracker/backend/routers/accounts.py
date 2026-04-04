from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from database import get_db
from models.account import Account, BrokerEnum

router = APIRouter(prefix="/accounts", tags=["accounts"])


class AccountCreate(BaseModel):
    name: str
    broker: BrokerEnum
    currency: str = "USD"
    notes: str | None = None


class AccountOut(BaseModel):
    id: int
    name: str
    broker: BrokerEnum
    currency: str
    notes: str | None

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[AccountOut])
async def list_accounts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Account).order_by(Account.broker, Account.name))
    return result.scalars().all()


@router.post("/", response_model=AccountOut, status_code=201)
async def create_account(payload: AccountCreate, db: AsyncSession = Depends(get_db)):
    account = Account(**payload.model_dump())
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


@router.delete("/{account_id}", status_code=204)
async def delete_account(account_id: int, db: AsyncSession = Depends(get_db)):
    account = await db.get(Account, account_id)
    if not account:
        raise HTTPException(404, "Account not found")
    await db.delete(account)
    await db.commit()
