import enum
from datetime import datetime
from sqlalchemy import String, DateTime, Enum as SAEnum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class BrokerEnum(str, enum.Enum):
    BINANCE = "binance"
    OSL = "osl"
    IBKR = "ibkr"
    FUTU = "futu"
    SOFI = "sofi"


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    broker: Mapped[BrokerEnum] = mapped_column(SAEnum(BrokerEnum), nullable=False)
    # Native currency of the account (e.g. USD for IBKR, HKD for Futu, USD for Binance)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    notes: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    positions: Mapped[list["Position"]] = relationship(back_populates="account", cascade="all, delete-orphan")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="account", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Account {self.broker.value}:{self.name}>"
