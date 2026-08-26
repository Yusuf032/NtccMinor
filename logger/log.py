import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

import requests
from dotenv import load_dotenv

load_dotenv()

"""This function is used to integrate Watchman logging service with other services."""
"""Watchman is an AI-powered log monitoring platform that revolutionizes log analysis and system monitoring.

    AI Chat Interface
    Query logs using natural language

    Real-time Monitoring
    Instant alerts and notifications


    Key Features
        - For DevOps Teams
        - Centralized log aggregation
        -  Real-time log analysis
        -  Error pattern detection
        -  Log-based alerting
        - For Developers
        -  Application log debugging
        -  Performance log insights
        -  Multi-language support
        -  Log ingestion APIs
    """

# ── Local file logger setup ───────────────────────────────────────────
_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "logs")
os.makedirs(_LOG_DIR, exist_ok=True)

_file_logger = logging.getLogger("curadocs_doctor_curabot")
_file_logger.setLevel(logging.DEBUG)

# Rotate at 10 KB, keep last 5 files
_handler = RotatingFileHandler(
    os.path.join(_LOG_DIR, "doctor_curabot.log"),
    maxBytes=100 * 1024,
    backupCount=10,
    encoding="utf-8",
)
_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
)
_file_logger.addHandler(_handler)

# Map custom level strings to Python logging levels
_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARN": logging.WARNING,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def logger(service: str, integration: str, level: str, priority: str, message: str):
    # ── 1. Always write to local log file ─────────────────────────────
    log_level = _LEVEL_MAP.get(level.upper(), logging.INFO)
    _file_logger.log(
        log_level,
        "[%s] [%s] [priority=%s] %s",
        service,
        integration,
        priority,
        message,
    )

    # ── 2. Send to remote Watchman service (best-effort) ──────────────
    try:
        response = requests.post(
            os.getenv("LOGGER_URL"),
            json={
                "account_id": os.getenv("Account_id"),
                "service": service,
                "integration": integration,
                "level": level,
                "priority": priority,
                "message": message,
            },
            headers={
                "WATCHMAN-API-KEY": os.getenv("Access_token"),
                "Content-Type": "application/json",
            },
            timeout=5,
        )
        return response.status_code == 200
    except requests.exceptions.ConnectionError:
        pass
    except Exception:
        pass
