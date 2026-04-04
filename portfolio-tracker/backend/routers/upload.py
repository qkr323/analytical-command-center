"""
PDF statement upload endpoint.

Flow:
1. Receive PDF + broker name
2. Parse PDF (pdfplumber → Claude Vision fallback)
3. For each position:
   a. Upsert Asset (compliance check)
   b. Upsert Position (overwrite with latest values)
   c. Take a PositionSnapshot for this statement date
4. For each transaction:
   a. Fingerprint check — skip if already imported
   b. Insert new transactions only
5. Return summary
"""
import hashlib
import os
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db
from models.account import Account
from models.asset import Asset, AssetTypeEnum, ComplianceStatusEnum
from models.compliance_review import ComplianceReview, ReviewStatusEnum
from models.position import Position
from models.position_snapshot import PositionSnapshot
from models.transaction import Transaction, TransactionTypeEnum
from services.compliance import check_symbol
from services.fx import convert_to_hkd
from services.parsers.base import RawPosition, RawTransaction
from services.pdf_parser import parse_statement

router = APIRouter(prefix="/upload", tags=["upload"])

os.makedirs(settings.upload_dir, exist_ok=True)


@router.post("/statement")
async def upload_statement(
    broker: str = Form(...),
    account_id: int = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Upload a broker PDF statement and import positions + transactions."""

    account = await db.get(Account, account_id)
    if not account:
        raise HTTPException(404, f"Account {account_id} not found")

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > 50 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 50 MB)")

    save_path = os.path.join(settings.upload_dir, f"{account_id}_{file.filename}")
    with open(save_path, "wb") as f:
        f.write(pdf_bytes)

    try:
        parsed = await parse_statement(pdf_bytes, broker, file.filename)
    except ValueError as e:
        raise HTTPException(422, str(e))

    snapshot_date = parsed.statement_date or date.today()

    summary: dict[str, Any] = {
        "broker": broker,
        "account_id": account_id,
        "filename": file.filename,
        "statement_date": snapshot_date.isoformat(),
        "positions_imported": 0,
        "positions_updated": 0,
        "transactions_imported": 0,
        "transactions_skipped_duplicate": 0,
        "flagged_for_review": [],
        "blocked": [],
        "legacy_hold": [],
        "warnings": parsed.parse_warnings,
    }

    for raw_pos in parsed.positions:
        await _process_position(db, account_id, raw_pos, file.filename, snapshot_date, summary)

    for raw_tx in parsed.transactions:
        await _process_transaction(db, account_id, raw_tx, file.filename, summary)

    await db.commit()
    return summary


# ── Asset helper ──────────────────────────────────────────────────────────────

async def _get_or_create_asset(
    db: AsyncSession,
    symbol: str,
    name: str | None,
    currency: str,
    hint_type: str | None,
) -> tuple[Asset, bool]:
    existing = await db.scalar(select(Asset).where(Asset.symbol == symbol.upper()))
    if existing:
        return existing, False

    compliance = check_symbol(symbol, hint_type)
    asset = Asset(
        symbol=symbol.upper(),
        name=name,
        currency=currency,
        asset_type=compliance.detected_type or AssetTypeEnum.UNKNOWN,
        compliance_status=compliance.status,
        compliance_reason=compliance.reason,
    )
    db.add(asset)
    await db.flush()
    return asset, True


# ── Position processing ───────────────────────────────────────────────────────

async def _process_position(
    db: AsyncSession,
    account_id: int,
    raw: RawPosition,
    filename: str,
    snapshot_date: date,
    summary: dict,
) -> None:
    if not raw.symbol:
        return

    asset, _ = await _get_or_create_asset(db, raw.symbol, raw.name, raw.currency, raw.asset_type_hint)

    if asset.compliance_status == ComplianceStatusEnum.BLOCKED:
        summary["blocked"].append({"symbol": raw.symbol, "reason": asset.compliance_reason})
        return

    if asset.compliance_status == ComplianceStatusEnum.LEGACY_HOLD:
        summary["legacy_hold"].append({"symbol": raw.symbol, "reason": asset.compliance_reason})
        # Fall through — legacy positions are still imported

    if asset.compliance_status == ComplianceStatusEnum.REVIEW_REQUIRED:
        existing_review = await db.scalar(
            select(ComplianceReview).where(
                ComplianceReview.asset_id == asset.id,
                ComplianceReview.status == ReviewStatusEnum.PENDING,
            )
        )
        if not existing_review:
            db.add(ComplianceReview(
                asset_id=asset.id,
                symbol=raw.symbol.upper(),
                flag_reason=asset.compliance_reason or "Unclassified asset",
                detected_type=asset.asset_type.value,
            ))
        summary["flagged_for_review"].append({"symbol": raw.symbol, "reason": asset.compliance_reason})
        return

    cost_hkd, fx_rate = await convert_to_hkd(db, raw.price or Decimal("0"), raw.currency)
    value_hkd, _ = await convert_to_hkd(db, raw.market_value or Decimal("0"), raw.currency)

    # Upsert current position
    existing_pos = await db.scalar(
        select(Position).where(Position.account_id == account_id, Position.asset_id == asset.id)
    )
    if existing_pos:
        existing_pos.quantity = raw.quantity
        existing_pos.avg_cost = raw.price
        existing_pos.cost_currency = raw.currency
        existing_pos.avg_cost_hkd = cost_hkd if raw.price else None
        existing_pos.last_price = raw.price
        existing_pos.last_price_hkd = cost_hkd if raw.price else None
        existing_pos.market_value_hkd = value_hkd if raw.market_value else None
        summary["positions_updated"] += 1
    else:
        db.add(Position(
            account_id=account_id,
            asset_id=asset.id,
            quantity=raw.quantity,
            avg_cost=raw.price,
            cost_currency=raw.currency,
            avg_cost_hkd=cost_hkd if raw.price else None,
            total_cost_hkd=(raw.quantity * cost_hkd) if raw.price else None,
            last_price=raw.price,
            last_price_hkd=cost_hkd if raw.price else None,
            market_value_hkd=value_hkd if raw.market_value else None,
        ))
        summary["positions_imported"] += 1

    # Upsert monthly snapshot (overwrite same date if re-uploaded)
    existing_snap = await db.scalar(
        select(PositionSnapshot).where(
            PositionSnapshot.snapshot_date == snapshot_date,
            PositionSnapshot.account_id == account_id,
            PositionSnapshot.asset_id == asset.id,
        )
    )
    if existing_snap:
        existing_snap.quantity = raw.quantity
        existing_snap.price_hkd = cost_hkd if raw.price else None
        existing_snap.market_value_hkd = value_hkd if raw.market_value else None
    else:
        db.add(PositionSnapshot(
            snapshot_date=snapshot_date,
            account_id=account_id,
            asset_id=asset.id,
            quantity=raw.quantity,
            price_hkd=cost_hkd if raw.price else None,
            market_value_hkd=value_hkd if raw.market_value else None,
            source_file=filename,
        ))


# ── Transaction processing ────────────────────────────────────────────────────

def _tx_fingerprint(account_id: int, raw: RawTransaction) -> str:
    """
    Deterministic fingerprint for a transaction.
    Two identical rows from different uploads produce the same hash → deduplication.
    """
    key = "|".join([
        str(account_id),
        str(raw.trade_date),
        str(raw.tx_type),
        str(raw.symbol or ""),
        str(raw.quantity or ""),
        str(raw.gross_amount or ""),
        str(raw.currency),
    ])
    return hashlib.sha256(key.encode()).hexdigest()


async def _process_transaction(
    db: AsyncSession,
    account_id: int,
    raw: RawTransaction,
    filename: str,
    summary: dict,
) -> None:
    asset_id = None
    if raw.symbol:
        asset, _ = await _get_or_create_asset(db, raw.symbol, None, raw.currency, raw.asset_type_hint)
        if asset.compliance_status == ComplianceStatusEnum.BLOCKED:
            return
        asset_id = asset.id

    fingerprint = _tx_fingerprint(account_id, raw)

    # Skip if already imported
    existing = await db.scalar(
        select(Transaction).where(Transaction.fingerprint == fingerprint)
    )
    if existing:
        summary["transactions_skipped_duplicate"] += 1
        return

    type_map = {
        "buy": TransactionTypeEnum.BUY,
        "sell": TransactionTypeEnum.SELL,
        "dividend": TransactionTypeEnum.DIVIDEND,
        "fee": TransactionTypeEnum.FEE,
        "deposit": TransactionTypeEnum.DEPOSIT,
        "withdrawal": TransactionTypeEnum.WITHDRAWAL,
        "transfer_in": TransactionTypeEnum.TRANSFER_IN,
        "transfer_out": TransactionTypeEnum.TRANSFER_OUT,
    }
    tx_type_enum = type_map.get(raw.tx_type.lower(), TransactionTypeEnum.FEE)

    tx_date = raw.trade_date
    price_hkd, fx_rate = await convert_to_hkd(db, raw.price or Decimal("0"), raw.currency, tx_date)
    gross_hkd, _ = await convert_to_hkd(db, raw.gross_amount or Decimal("0"), raw.currency, tx_date)
    fee_hkd, _ = await convert_to_hkd(db, raw.fee, raw.currency, tx_date)
    net_amount = (raw.gross_amount or Decimal("0")) - raw.fee
    net_hkd, _ = await convert_to_hkd(db, net_amount, raw.currency, tx_date)

    db.add(Transaction(
        account_id=account_id,
        asset_id=asset_id,
        tx_type=tx_type_enum,
        trade_date=tx_date,
        quantity=raw.quantity,
        price=raw.price,
        gross_amount=raw.gross_amount,
        fee=raw.fee,
        net_amount=net_amount,
        currency=raw.currency,
        fx_rate_to_hkd=fx_rate,
        price_hkd=price_hkd if raw.price else None,
        gross_amount_hkd=gross_hkd if raw.gross_amount else None,
        fee_hkd=fee_hkd,
        net_amount_hkd=net_hkd,
        source_file=filename,
        notes=raw.notes,
        fingerprint=fingerprint,
    ))

    summary["transactions_imported"] += 1
