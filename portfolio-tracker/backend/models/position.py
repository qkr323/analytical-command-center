from datetime import datetime
from decimal import Decimal
from sqlalchemy import ForeignKey, Numeric, String, DateTime, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class Position(Base):
    """Current holding in a specific account."""
    __tablename__ = "positions"
    __table_args__ = (UniqueConstraint("account_id", "asset_id", name="uq_account_asset"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False, index=True)

    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)

    # Cost basis in original currency
    avg_cost: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    cost_currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")

    # Cost basis converted to HKD (base currency)
    avg_cost_hkd: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    total_cost_hkd: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))

    # Original-currency values — used to recalculate HKD on FX refresh
    # (positionValue / ending_cash / market_value direct from broker)
    market_value_local: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    total_cost_local: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))

    # Latest market price (refreshed by price service)
    last_price: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    last_price_hkd: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    market_value_hkd: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))

    # P&L
    unrealized_pnl_hkd: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    unrealized_pnl_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))

    last_updated: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    account: Mapped["Account"] = relationship(back_populates="positions")
    asset: Mapped["Asset"] = relationship(back_populates="positions")

    def __repr__(self) -> str:
        return f"<Position account={self.account_id} asset={self.asset_id} qty={self.quantity}>"
