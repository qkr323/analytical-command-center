from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import String, Date, Numeric, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class FxRate(Base):
    """Daily FX rates. Base currency is HKD — all rates are X per 1 HKD."""
    __tablename__ = "fx_rates"
    __table_args__ = (UniqueConstraint("rate_date", "from_currency", name="uq_date_currency"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    rate_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    from_currency: Mapped[str] = mapped_column(String(10), nullable=False)  # e.g. "USD"
    to_currency: Mapped[str] = mapped_column(String(10), nullable=False, default="HKD")
    rate: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)  # 1 from_currency = rate HKD
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"<FxRate {self.from_currency}/{self.to_currency} = {self.rate} on {self.rate_date}>"
