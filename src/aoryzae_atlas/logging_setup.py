"""Logging configuration shared by the CLI and all pipeline modules.

Per PROJECT_MASTER_SPEC.md section 26: every important operation must be
logged, with enough detail to answer "exactly how was this value generated".
Logs are written both to the console and to a rotating file under
results/logs/, so history survives across CLI invocations.
"""
from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from .paths import LOGS_DIR

_CONFIGURED = False


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    global _CONFIGURED
    logger = logging.getLogger("aoryzae_atlas")
    if _CONFIGURED:
        return logger

    logger.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            Path(LOGS_DIR) / "atlas.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
    except OSError:
        # Logging to disk is best-effort; never let it block the CLI.
        logger.warning("Could not open log file under %s; console-only logging.", LOGS_DIR)

    _CONFIGURED = True
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    configure_logging()
    return logging.getLogger(f"aoryzae_atlas.{name}" if name else "aoryzae_atlas")
