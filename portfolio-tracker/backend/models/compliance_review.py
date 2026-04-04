import enum
from datetime import datetime
from sqlalchemy import String, DateTime, Enum as SAEnum, func, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class ReviewStatusEnum(str, enum.Enum):
    PENDING = "pending"       # Awaiting your review
    APPROVED = "approved"     # You manually approved — asset becomes ALLOWED
    REJECTED = "rejected"     # You manually rejected — asset stays BLOCKED


class ComplianceReview(Base):
    """
    Items flagged for manual review under the block-and-ask approach.
    When an unknown ETF or ambiguous asset is encountered, it lands here.
    You review, approve or reject, and the asset's compliance_status is updated.
    """
    __tablename__ = "compliance_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)

    # Why it was flagged
    flag_reason: Mapped[str] = mapped_column(String(500), nullable=False)

    # Classification attempt info (what we could determine automatically)
    detected_type: Mapped[str | None] = mapped_column(String(100))
    etf_constituents: Mapped[str | None] = mapped_column(String(50))   # e.g. "45 holdings"
    etf_top_sector: Mapped[str | None] = mapped_column(String(100))    # e.g. "Technology 72%"
    etf_index_tracked: Mapped[str | None] = mapped_column(String(100))

    status: Mapped[ReviewStatusEnum] = mapped_column(
        SAEnum(ReviewStatusEnum), nullable=False, default=ReviewStatusEnum.PENDING
    )
    reviewer_notes: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"<ComplianceReview {self.symbol} — {self.status.value}>"
