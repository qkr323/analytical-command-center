"""Interest and dividend accrual models."""
from datetime import date
from decimal import Decimal

from sqlalchemy import Column, Integer, String, Numeric, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from database import Base


class InterestAccrual(Base):
    """Accrued interest per currency (IBKR)."""
    __tablename__ = "interest_accruals"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    currency = Column(String(10), nullable=False)

    starting_balance = Column(Numeric(16, 8), default=0)
    interest_accrued = Column(Numeric(16, 8), default=0)
    accrual_reversal = Column(Numeric(16, 8), default=0)
    fx_translation = Column(Numeric(16, 8), default=0)
    ending_balance = Column(Numeric(16, 8), default=0)

    snapshot_date = Column(Date, nullable=False)
    synced_at = Column(Date, nullable=False)
    source = Column(String(50), default="ibkr_flex_api")

    account = relationship("Account", back_populates="interest_accruals")

    __table_args__ = (UniqueConstraint("account_id", "currency", "snapshot_date", name="uq_interest_accrual_per_date"),)


class DividendAccrual(Base):
    """Open/upcoming dividend accruals (IBKR)."""
    __tablename__ = "dividend_accruals"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)

    symbol = Column(String(50), nullable=False)
    description = Column(String(255))
    currency = Column(String(10), nullable=False)
    asset_category = Column(String(20))

    quantity = Column(Numeric(16, 8), nullable=False)
    ex_date = Column(Date)
    pay_date = Column(Date)
    gross_rate = Column(Numeric(16, 8))
    gross_amount = Column(Numeric(16, 8), default=0)
    tax = Column(Numeric(16, 8), default=0)
    fee = Column(Numeric(16, 8), default=0)
    net_amount = Column(Numeric(16, 8), default=0)

    snapshot_date = Column(Date, nullable=False)
    synced_at = Column(Date, nullable=False)
    source = Column(String(50), default="ibkr_flex_api")

    account = relationship("Account", back_populates="dividend_accruals")
    asset = relationship("Asset")

    __table_args__ = (
        UniqueConstraint("account_id", "asset_id", "ex_date", "pay_date", name="uq_dividend_accrual_per_date"),
    )
