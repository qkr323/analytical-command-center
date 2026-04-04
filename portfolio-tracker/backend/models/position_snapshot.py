from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import ForeignKey, Numeric, String, Date, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class PositionSnapshot(Base):
    """
    Monthly snapshot of each position taken at statement upload time.
    Enables month-over-month comparison and NAV history.
    """
    __tablename__ = "position_snapshots"
    __table_args__ = (
        UniqueConstraint("snapshot_date", "account_id", "asset_id", name="uq_snapshot_account_asset"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)

    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    price_hkd: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    market_value_hkd: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    cost_hkd: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))

    source_file: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    account: Mapped["Account"] = relationship()
    asset: Mapped["Asset"] = relationship()
