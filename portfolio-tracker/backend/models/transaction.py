import enum
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import ForeignKey, Numeric, String, DateTime, Date, Enum as SAEnum, func, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class TransactionTypeEnum(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"
    DIVIDEND = "dividend"
    FEE = "fee"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    INTEREST = "interest"
    SPLIT = "split"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("assets.id"), index=True)  # null for cash transactions

    tx_type: Mapped[TransactionTypeEnum] = mapped_column(SAEnum(TransactionTypeEnum), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    settle_date: Mapped[date | None] = mapped_column(Date)

    quantity: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))

    # Original currency values
    price: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    gross_amount: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    fee: Mapped[Decimal] = mapped_column(Numeric(28, 10), default=0)
    net_amount: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")

    # HKD equivalents (converted at trade date FX rate)
    fx_rate_to_hkd: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    price_hkd: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    gross_amount_hkd: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    fee_hkd: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    net_amount_hkd: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))

    # Realized P&L — populated by services/pnl.py using average-cost method
    realized_pnl_local: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    realized_pnl_hkd: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    cost_basis_local: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    cost_basis_hkd: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    avg_cost_per_unit_local: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    avg_cost_per_unit_hkd: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    cost_basis_method: Mapped[str | None] = mapped_column(String(50))
    calculation_version: Mapped[str | None] = mapped_column(String(20))
    data_quality_flag: Mapped[str | None] = mapped_column(String(50))
    pnl_calculated_at: Mapped[datetime | None] = mapped_column(DateTime)
    exclude_from_pnl_totals: Mapped[bool] = mapped_column(default=False, server_default="false")

    # Audit
    source_file: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    # SHA-256 fingerprint for deduplication — same transaction across re-uploads = same hash
    fingerprint: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    account: Mapped["Account"] = relationship(back_populates="transactions")
    asset: Mapped["Asset"] = relationship(back_populates="transactions")

    def __repr__(self) -> str:
        return f"<Transaction {self.tx_type.value} {self.asset_id} qty={self.quantity} date={self.trade_date}>"
