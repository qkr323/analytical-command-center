import enum
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Enum as SAEnum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class AssetTypeEnum(str, enum.Enum):
    # Equities
    STOCK = "stock"                     # Single name — BLOCKED
    ETF_BROAD_INDEX = "etf_broad_index" # SPY, QQQ, VTI — ALLOWED
    ETF_COMMODITY = "etf_commodity"     # GLD, SLV, DJP — ALLOWED
    ETF_BOND = "etf_bond"               # TLT, AGG — ALLOWED
    ETF_SECTOR = "etf_sector"           # XLE, SMH — BLOCKED
    ETF_THEMATIC = "etf_thematic"       # ARKK — BLOCKED
    ETF_UNKNOWN = "etf_unknown"         # Unclassified — REVIEW REQUIRED
    # Fixed income
    BOND_UST = "bond_ust"               # US Treasuries — ALLOWED
    BOND_UKT = "bond_ukt"               # UK Gilts — ALLOWED
    BOND_ACGB = "bond_acgb"             # Australian Govt Bonds — ALLOWED
    BOND_OTHER = "bond_other"           # Other bonds — BLOCKED
    # Crypto
    CRYPTO = "crypto"                   # All crypto — ALLOWED
    # Derivatives
    OPTION_INDEX = "option_index"       # Index options — REVIEW (may be allowed)
    OPTION_SINGLE = "option_single"     # Single name options — BLOCKED
    FUTURE_COMMODITY = "future_commodity"  # Commodity futures — REVIEW
    FUTURE_SINGLE = "future_single"     # Single name futures — BLOCKED
    # Other
    CASH = "cash"
    UNKNOWN = "unknown"


class ComplianceStatusEnum(str, enum.Enum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    REVIEW_REQUIRED = "review_required"  # block-and-ask: blocked until manually approved
    LEGACY_HOLD = "legacy_hold"          # pre-existing position (before joining firm) — hold/sell OK, no new buys


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    asset_type: Mapped[AssetTypeEnum] = mapped_column(SAEnum(AssetTypeEnum), nullable=False, default=AssetTypeEnum.UNKNOWN)
    exchange: Mapped[str | None] = mapped_column(String(30))   # e.g. NASDAQ, HKEX, BINANCE
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")

    # Compliance
    compliance_status: Mapped[ComplianceStatusEnum] = mapped_column(
        SAEnum(ComplianceStatusEnum),
        nullable=False,
        default=ComplianceStatusEnum.REVIEW_REQUIRED,
    )
    compliance_reason: Mapped[str | None] = mapped_column(String(500))

    # ETF metadata (populated when asset_type is an ETF variant)
    etf_constituents_count: Mapped[int | None] = mapped_column(Integer)
    etf_index_tracked: Mapped[str | None] = mapped_column(String(100))

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    positions: Mapped[list["Position"]] = relationship(back_populates="asset")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="asset")

    def __repr__(self) -> str:
        return f"<Asset {self.symbol} ({self.asset_type.value}) — {self.compliance_status.value}>"
