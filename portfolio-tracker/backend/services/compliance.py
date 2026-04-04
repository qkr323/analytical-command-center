"""
Compliance checker — block-and-ask approach.

Rules (hedge fund employee):
  ALLOWED  : broad index ETFs, commodity ETFs, bond ETFs,
             UST / UKT / ACGB direct bonds, all crypto
  BLOCKED  : single name stocks, single name options/futures,
             sector ETFs, thematic ETFs, other bonds
  REVIEW   : unknown ETFs, ambiguous instruments → blocked until manually approved
"""
from dataclasses import dataclass
from models.asset import AssetTypeEnum, ComplianceStatusEnum

# ── Known-allowed ETFs ────────────────────────────────────────────────────────

BROAD_INDEX_ETFS: set[str] = {
    # US broad market
    "SPY", "IVV", "VOO",          # S&P 500
    "QQQ", "QQQM",                # Nasdaq-100
    "VTI", "ITOT", "SCHB",        # US total market
    "DIA",                         # Dow Jones
    "IWM", "VB", "VTWO",          # Small cap
    "VXF",                         # Extended market (ex S&P500)
    # International broad
    "EEM", "VWO", "IEMG",         # Emerging markets
    "EFA", "VEA", "SCHF",         # Developed ex-US
    "VEU", "VXUS", "IXUS",        # All-world ex-US
    "VT", "ACWI", "URTH",         # All-world
    # Factor / style (broad enough — multi-sector)
    "VTV", "VUG", "IWD", "IWF",   # Value / Growth
    "MTUM", "VLUE", "USMV",       # Factor ETFs
    "QUAL",                         # Quality factor
    # HK listed broad index
    "2800.HK", "2823.HK", "3188.HK",  # Tracker Fund HK, CSOP A50
    # Asia / HK broad
    "EWH",                          # iShares MSCI Hong Kong (broad)
    "MCHI",                         # iShares MSCI China (broad index)
    "FXI",                          # iShares China Large-Cap (broad)
    # Fixed income broad (tracked as ETF_BOND separately, listed here for completeness)
}

COMMODITY_ETFS: set[str] = {
    "GLD", "IAU", "SGOL", "AAAU",  # Gold
    "SLV", "SIVR",                  # Silver
    "USO", "BNO",                   # Oil
    "DBA",                           # Agriculture
    "DJP", "PDBC", "DBC", "COMT",  # Broad commodities
    "CPER",                          # Copper
    "WEAT", "CORN", "SOYB",         # Agricultural
    "UNG",                           # Natural gas
    "PALL", "PPLT",                  # Palladium, Platinum
    "DBB",                           # Base metals
}

BOND_ETFS: set[str] = {
    "TLT", "IEF", "SHY", "VGIT", "GOVT", "SCHO",  # US Treasuries (long/intermediate)
    "VGSH", "SGOV", "BIL",                          # US Treasuries (short-term)
    "EDV",                                           # Vanguard Extended Duration Treasury ETF
    "2561.T", "2562.T",                              # iShares JP Govt Bond ETF (Tokyo)
    "AGG", "BND", "SCHZ", "IUSB",                   # US broad bond
    "LQD", "VCIT", "IGIB",                           # IG corporate
    "HYG", "JNK", "USHY",                            # High yield
    "BNDX", "IAGG", "BWX",                           # International bonds
    "TIP", "STIP", "VTIP",                            # TIPS / inflation
    "MUB", "SUB",                                     # Municipal
    "EMB", "VWOB",                                    # EM sovereign bonds
    "FLOT", "NEAR",                                   # Short duration / floating
}

# ── Known-blocked ETFs ────────────────────────────────────────────────────────

SECTOR_ETFS: set[str] = {
    # SPDR sector suite
    "XLE", "XLK", "XLF", "XLV", "XLI", "XLB", "XLU", "XLC", "XLRE", "XLP", "XLY",
    # iShares sector
    "IYW", "IYF", "IYH", "IYE", "IYZ",
    # Vanguard sector
    "VGT", "VFH", "VHT", "VDE", "VOX", "VPU", "VAW", "VCR", "VDC", "VNQ",
}

THEMATIC_ETFS: set[str] = {
    "ARKK", "ARKQ", "ARKG", "ARKW", "ARKF", "ARKX",  # ARK funds
    "SMH", "SOXX",                                      # Semiconductors
    "ICLN", "QCLN", "ACES",                             # Clean energy
    "HACK", "CIBR", "BUG",                              # Cybersecurity
    "ROBO", "BOTZ", "IRBO",                             # Robotics / AI
    "JETS",                                              # Airlines
    "ESPO",                                              # Video games
    "FINX",                                              # Fintech
    "IBB", "XBI",                                        # Biotech
    "BLOK",                                              # Blockchain
    "BITO",                                              # Bitcoin futures ETF
    "KWEB", "CQQQ",                                      # China internet/tech
    "LIT", "BATT",                                       # Lithium & battery tech
    "USO", "BNO", "UCO",                                 # Oil (single commodity, not broad)
    "512170",                                            # Hwabao WP CSI Medical Service ETF (SSE)
}

# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ComplianceResult:
    status: ComplianceStatusEnum
    reason: str
    detected_type: AssetTypeEnum | None = None


def check_symbol(symbol: str, hint_type: str | None = None) -> ComplianceResult:
    """
    Synchronous compliance check for a single symbol.
    hint_type: optional string from the broker parser ("stock", "etf", "crypto", etc.)

    Returns a ComplianceResult. Blocked items must not be traded.
    REVIEW_REQUIRED items are blocked until manually approved via the compliance review UI.
    """
    sym = symbol.upper().strip()

    # ── Cash positions ───────────────────────────────────────────────────────
    if hint_type == "cash" or sym.endswith(".CASH"):
        return ComplianceResult(
            status=ComplianceStatusEnum.ALLOWED,
            reason="Cash balance — always permitted.",
            detected_type=AssetTypeEnum.CASH,
        )

    # ── Money market funds (Futu ISIN-coded funds) ───────────────────────────
    # These are capital-preservation instruments equivalent to cash.
    if hint_type == "money_market" or _is_money_market_fund(sym):
        return ComplianceResult(
            status=ComplianceStatusEnum.ALLOWED,
            reason="Money market fund — treated as cash equivalent, permitted.",
            detected_type=AssetTypeEnum.CASH,
        )

    # ── Crypto ──────────────────────────────────────────────────────────────
    if hint_type == "crypto" or _is_crypto(sym):
        return ComplianceResult(
            status=ComplianceStatusEnum.ALLOWED,
            reason="Crypto is permitted.",
            detected_type=AssetTypeEnum.CRYPTO,
        )

    # ── Government bonds ────────────────────────────────────────────────────
    bond_type = _classify_govt_bond(sym)
    if bond_type:
        return ComplianceResult(
            status=ComplianceStatusEnum.ALLOWED,
            reason=f"Government bond ({bond_type.value}) is permitted.",
            detected_type=bond_type,
        )

    # ── Single name stocks ──────────────────────────────────────────────────
    if hint_type == "stock":
        return ComplianceResult(
            status=ComplianceStatusEnum.LEGACY_HOLD,
            reason=(
                "Single name stock — new purchases are not permitted. "
                "Pre-existing positions (held before joining the firm) may be retained and sold."
            ),
            detected_type=AssetTypeEnum.STOCK,
        )

    # ── Options ─────────────────────────────────────────────────────────────
    if hint_type in ("option", "option_single"):
        return ComplianceResult(
            status=ComplianceStatusEnum.BLOCKED,
            reason="Single name options are not permitted.",
            detected_type=AssetTypeEnum.OPTION_SINGLE,
        )

    # ── Futures ─────────────────────────────────────────────────────────────
    if hint_type in ("future", "future_single"):
        return ComplianceResult(
            status=ComplianceStatusEnum.BLOCKED,
            reason="Single name futures are not permitted.",
            detected_type=AssetTypeEnum.FUTURE_SINGLE,
        )

    # ── ETF classification ──────────────────────────────────────────────────
    if hint_type == "etf" or sym in _all_known_etfs():
        return _classify_etf(sym)

    # ── Unknown ─────────────────────────────────────────────────────────────
    return ComplianceResult(
        status=ComplianceStatusEnum.REVIEW_REQUIRED,
        reason=(
            f"'{sym}' could not be automatically classified. "
            "Blocked pending your manual review."
        ),
        detected_type=AssetTypeEnum.UNKNOWN,
    )


def _classify_etf(sym: str) -> ComplianceResult:
    if sym in BROAD_INDEX_ETFS:
        return ComplianceResult(
            status=ComplianceStatusEnum.ALLOWED,
            reason="Broad market index ETF — permitted.",
            detected_type=AssetTypeEnum.ETF_BROAD_INDEX,
        )
    if sym in COMMODITY_ETFS:
        return ComplianceResult(
            status=ComplianceStatusEnum.ALLOWED,
            reason="Commodity ETF — permitted.",
            detected_type=AssetTypeEnum.ETF_COMMODITY,
        )
    if sym in BOND_ETFS:
        return ComplianceResult(
            status=ComplianceStatusEnum.ALLOWED,
            reason="Bond ETF — permitted.",
            detected_type=AssetTypeEnum.ETF_BOND,
        )
    if sym in SECTOR_ETFS:
        return ComplianceResult(
            status=ComplianceStatusEnum.BLOCKED,
            reason="Sector ETF — not permitted (concentrated single-sector exposure).",
            detected_type=AssetTypeEnum.ETF_SECTOR,
        )
    if sym in THEMATIC_ETFS:
        return ComplianceResult(
            status=ComplianceStatusEnum.BLOCKED,
            reason="Thematic ETF — not permitted (concentrated thematic exposure).",
            detected_type=AssetTypeEnum.ETF_THEMATIC,
        )
    # ETF but not in any known list → block and ask
    return ComplianceResult(
        status=ComplianceStatusEnum.REVIEW_REQUIRED,
        reason=(
            f"ETF '{sym}' is not in the known-allowed lists. "
            "Blocked pending your manual review to confirm it qualifies as a broad index, "
            "commodity, or bond ETF."
        ),
        detected_type=AssetTypeEnum.ETF_UNKNOWN,
    )


def _is_crypto(sym: str) -> bool:
    crypto_suffixes = ("USDT", "BTC", "ETH", "BNB", "BUSD", "USDC")
    crypto_bases = {"BTC", "ETH", "BNB", "SOL", "ADA", "XRP", "DOGE", "AVAX", "DOT", "MATIC", "LINK", "UNI", "AAVE"}
    return sym in crypto_bases or any(sym.endswith(s) for s in crypto_suffixes)


def _classify_govt_bond(sym: str) -> AssetTypeEnum | None:
    ust_patterns = ("UST", "TBILL", "TNOTE", "TBOND", "US TREASURY", "912")  # CUSIP prefix
    ukt_patterns = ("UKT", "UK GILT", "GILT")
    acgb_patterns = ("ACGB", "AUST GOVT", "AUSTRALIAN GOVT")

    sym_upper = sym.upper()
    if any(p in sym_upper for p in ust_patterns):
        return AssetTypeEnum.BOND_UST
    if any(p in sym_upper for p in ukt_patterns):
        return AssetTypeEnum.BOND_UKT
    if any(p in sym_upper for p in acgb_patterns):
        return AssetTypeEnum.BOND_ACGB
    return None


def _all_known_etfs() -> set[str]:
    return BROAD_INDEX_ETFS | COMMODITY_ETFS | BOND_ETFS | SECTOR_ETFS | THEMATIC_ETFS


def _is_money_market_fund(sym: str) -> bool:
    """
    Detect money market / liquidity funds by symbol pattern.
    Futu uses ISIN-style codes (e.g. HK0000857273) for funds.
    We also catch common money market fund name keywords.
    """
    import re
    # ISIN-format fund codes from Futu (12-char alphanumeric starting with country code)
    if re.match(r'^[A-Z]{2}\d{10}$', sym):
        return True
    # Name-based keywords (passed via hint_type or embedded in symbol)
    money_market_keywords = ("MONEY MARKET", "MONEYMKT", "MMKT", "LIQUIDITY FUND",
                              "CASH FUND", "TREASURY FUND")
    return any(kw in sym for kw in money_market_keywords)
