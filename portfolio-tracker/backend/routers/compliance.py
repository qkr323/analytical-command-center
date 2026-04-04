"""
Compliance endpoints.

GET  /compliance/check?symbol=ARKK        — pre-trade check for any symbol
GET  /compliance/reviews                  — list all pending review items
POST /compliance/reviews/{id}/approve     — approve a flagged asset
POST /compliance/reviews/{id}/reject      — reject a flagged asset
GET  /compliance/blocked                  — list blocked assets currently in portfolio
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.asset import Asset, ComplianceStatusEnum
from models.compliance_review import ComplianceReview, ReviewStatusEnum
from services.compliance import check_symbol

router = APIRouter(prefix="/compliance", tags=["compliance"])


class CheckResult(BaseModel):
    symbol: str
    status: str
    reason: str
    detected_type: str | None


class ReviewOut(BaseModel):
    id: int
    symbol: str
    flag_reason: str
    detected_type: str | None
    etf_constituents: str | None
    etf_top_sector: str | None
    etf_index_tracked: str | None
    status: str
    reviewer_notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewDecision(BaseModel):
    notes: str | None = None


@router.get("/check", response_model=CheckResult)
async def check_compliance(symbol: str, hint_type: str | None = None, action: str = "buy"):
    """
    Pre-trade compliance check. Does not touch the database.
    action: "buy" or "sell" — selling a legacy_hold position is always permitted.
    """
    result = check_symbol(symbol, hint_type)

    # Selling a legacy_hold is always allowed
    if result.status.value == "legacy_hold" and action.lower() == "sell":
        return CheckResult(
            symbol=symbol.upper(),
            status="allowed",
            reason="Selling a legacy (pre-firm) position is permitted.",
            detected_type=result.detected_type.value if result.detected_type else None,
        )

    return CheckResult(
        symbol=symbol.upper(),
        status=result.status.value,
        reason=result.reason,
        detected_type=result.detected_type.value if result.detected_type else None,
    )


@router.get("/reviews", response_model=list[ReviewOut])
async def list_reviews(
    status: str = "pending",
    db: AsyncSession = Depends(get_db),
):
    """List compliance review items. Default: pending items only."""
    try:
        status_enum = ReviewStatusEnum(status)
    except ValueError:
        raise HTTPException(400, f"Invalid status '{status}'. Must be: pending, approved, rejected")

    result = await db.execute(
        select(ComplianceReview)
        .where(ComplianceReview.status == status_enum)
        .order_by(ComplianceReview.created_at.desc())
    )
    return result.scalars().all()


@router.post("/reviews/{review_id}/approve", response_model=ReviewOut)
async def approve_review(
    review_id: int,
    payload: ReviewDecision,
    db: AsyncSession = Depends(get_db),
):
    """Approve a flagged asset — marks it as ALLOWED in the assets table."""
    review = await db.get(ComplianceReview, review_id)
    if not review:
        raise HTTPException(404, "Review not found")
    if review.status != ReviewStatusEnum.PENDING:
        raise HTTPException(400, f"Review is already {review.status.value}")

    review.status = ReviewStatusEnum.APPROVED
    review.reviewer_notes = payload.notes
    review.reviewed_at = datetime.utcnow()

    # Update the asset's compliance status
    asset = await db.get(Asset, review.asset_id)
    if asset:
        asset.compliance_status = ComplianceStatusEnum.ALLOWED
        asset.compliance_reason = f"Manually approved. Notes: {payload.notes or 'none'}"

    await db.commit()
    await db.refresh(review)
    return review


@router.post("/reviews/{review_id}/reject", response_model=ReviewOut)
async def reject_review(
    review_id: int,
    payload: ReviewDecision,
    db: AsyncSession = Depends(get_db),
):
    """Reject a flagged asset — keeps it BLOCKED."""
    review = await db.get(ComplianceReview, review_id)
    if not review:
        raise HTTPException(404, "Review not found")
    if review.status != ReviewStatusEnum.PENDING:
        raise HTTPException(400, f"Review is already {review.status.value}")

    review.status = ReviewStatusEnum.REJECTED
    review.reviewer_notes = payload.notes
    review.reviewed_at = datetime.utcnow()

    asset = await db.get(Asset, review.asset_id)
    if asset:
        asset.compliance_status = ComplianceStatusEnum.BLOCKED
        asset.compliance_reason = f"Manually rejected. Notes: {payload.notes or 'none'}"

    await db.commit()
    await db.refresh(review)
    return review


@router.get("/blocked", response_model=list[dict])
async def list_blocked_assets(db: AsyncSession = Depends(get_db)):
    """List all blocked assets that are currently in the portfolio (shouldn't be held)."""
    from models.position import Position
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Asset)
        .join(Asset.positions)
        .where(
            Asset.compliance_status == ComplianceStatusEnum.BLOCKED,
            Position.quantity > 0,
        )
        .options(selectinload(Asset.positions))
    )
    assets = result.scalars().unique().all()

    return [
        {
            "symbol": a.symbol,
            "name": a.name,
            "compliance_reason": a.compliance_reason,
            "positions_count": len([p for p in a.positions if p.quantity > 0]),
        }
        for a in assets
    ]
