# ============================================================
# ProctorAI — utils/helpers.py
#
# CHANGES:
#   1. generate_session_id() now appends a 6-char UUID hex suffix
#      to guarantee uniqueness even when two sessions start within
#      the same second.
# ============================================================

import os
import uuid
import logging
from datetime import datetime

from config.settings import RISK_LOW_MAX, RISK_MEDIUM_MAX
from utils.constants import RISK_LOW, RISK_MEDIUM, RISK_HIGH


def get_logger(name: str) -> logging.Logger:
    """Return a standardised logger for any module."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
            datefmt="%H:%M:%S",
        ))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


def now_str() -> str:
    return datetime.now().strftime("%H:%M:%S")


def now_dt() -> datetime:
    return datetime.now()


def generate_session_id() -> str:
    """
    Generate a unique exam session ID.
    Format: SES_YYYYMMDD_HHMMSS_XXXXXX  (XXXXXX = 6 random hex chars)
    FIX: UUID suffix prevents collisions when two sessions start
    in the same second (e.g. rapid test restarts).
    """
    ts  = datetime.now().strftime("SES_%Y%m%d_%H%M%S")
    uid = uuid.uuid4().hex[:6].upper()
    return f"{ts}_{uid}"


def risk_label(score: int) -> str:
    if score <= RISK_LOW_MAX:
        return RISK_LOW
    if score <= RISK_MEDIUM_MAX:
        return RISK_MEDIUM
    return RISK_HIGH


def risk_color(score: int) -> str:
    if score <= RISK_LOW_MAX:
        return "green"
    if score <= RISK_MEDIUM_MAX:
        return "orange"
    return "red"


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def format_duration(seconds: int) -> str:
    m, s = divmod(max(0, seconds), 60)
    return f"{m:02d}:{s:02d}"

def format_time(seconds: int) -> str:
    return format_duration(seconds)

def setup_directories():
    """Ensure all required data directories exist.

    Paths match config/settings.py: REPORTS_DIR, SCREENSHOTS_DIR,
    LOGS_DIR, EXPORTS_DIR — all live at project root, not under data/.
    """
    from config.settings import (
        REPORTS_DIR, SCREENSHOTS_DIR, LOGS_DIR, EXPORTS_DIR
    )
    for d in (REPORTS_DIR, SCREENSHOTS_DIR, LOGS_DIR, EXPORTS_DIR):
        ensure_dir(d)
