#!/usr/bin/env python3
"""SQLite connection + schema init, and the finding-normalization helpers
shared by ingestion and retrieval. Stdlib only."""
import hashlib
import re
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("knowledge.db")
SCHEMA = Path(__file__).with_name("schema.sql")


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    return conn


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()


# --- normalization -------------------------------------------------------

_SEV = [
    ("critical", r"\bcritical\b|\[c-?\d"),
    ("high", r"\bhigh\b|\[h-?\d"),
    ("medium", r"\bmedium\b|\bmed\b|\[m-?\d"),
    ("low", r"\blow\b|\[l-?\d"),
    ("info", r"\binfo(rmational)?\b|\bgas\b|\bqa\b|\bnc\b|\[i-?\d|\[g-?\d"),
]


def norm_severity(text: str) -> str:
    t = (text or "").lower()
    for name, pat in _SEV:
        if re.search(pat, t):
            return name
    return "unknown"


# category keyword map -> normalized taxonomy category. First match wins, so
# order from most-specific to least. ponytail: keyword heuristic; swap for an
# embedding classifier if precision matters.
_CATEGORY = [
    ("reentrancy", r"reentran|re-entran|cross-function call|checks-effects"),
    ("oracle-manipulation", r"oracle|price manipulat|twap|chainlink|spot price|flash ?loan.*price"),
    ("access-control", r"access control|authoriz|only ?owner|permission|privilege|missing.*modifier|unprotected"),
    ("arithmetic-rounding", r"rounding|precision|overflow|underflow|truncat|division|decimals|loss of precision"),
    ("share-inflation", r"inflation attack|first deposit|share price|erc4626|vault share"),
    ("signature-replay", r"signature|ecrecover|replay|eip-?712|nonce|malleab"),
    ("initialization-upgrade", r"initializ|uninitializ|upgrade|proxy|delegatecall|storage collision"),
    ("dos", r"denial of service|\bdos\b|unbounded loop|gas limit|griefing|stuck fund|block.*transaction"),
    ("token-assumption", r"fee-on-transfer|fee on transfer|rebas|non-standard token|safeerc20|return value|usdt"),
    ("accounting", r"accounting|balanceof|double count|incorrect balance|internal balance"),
    ("account-validation", r"owner check|signer|is_signer|pda|writable|account substitut|confused deputy|discriminator|anchor"),
    ("cpi", r"\bcpi\b|cross-program|invoke_signed|arbitrary program"),
    ("mev-frontrun", r"front-?run|sandwich|\bmev\b|slippage|deadline"),
    ("state-transition", r"invariant|state transition|liquidat|wrong order|phase"),
    ("unsafe-ffi", r"\bunsafe\b|\bffi\b|transmute|raw pointer|undefined behav"),
    ("input-validation", r"input validation|deserializ|borsh|bincode|bounds check|out of bounds"),
]


def categorize(title: str, body: str) -> str:
    t = f"{title}\n{body}".lower()
    for name, pat in _CATEGORY:
        if re.search(pat, t):
            return name
    return "uncategorized"


def detect_lang_ecosystem(text: str) -> tuple[str, str]:
    t = (text or "").lower()
    if re.search(r"\bsolana\b|anchor|\bpda\b|lamports|invoke_signed|\.rs\b", t):
        return ("rust", "solana")
    if re.search(r"\brust\b|cargo|\.rs\b|borsh", t):
        return ("rust", "unknown")
    if re.search(r"solidity|\.sol\b|evm|erc-?20|erc-?721|ethereum|uniswap", t):
        return ("solidity", "evm")
    return ("unknown", "unknown")
