"""Structured logging for Kalka using structlog.

All logging stays local — no network I/O, no telemetry, no data collection.
Logs go to stderr by default, and optionally to a local file via --log-file.

Usage:
    from .logger import get_logger
    log = get_logger()
    log.info("scan_started", tool="duplicate_files", dirs=["/home"])
"""

import logging
import sys
from pathlib import Path

import structlog


def init(level: str = "WARNING", log_file: str | None = None):
    """Configure structlog. Call once at startup before any logging."""

    # Map string level to stdlib constant
    numeric_level = getattr(logging, level.upper(), logging.WARNING)

    # Shared processors for both console and file output
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    handlers: list[logging.Handler] = []

    # Console handler — human-readable when attached to a terminal,
    # JSON otherwise (e.g. when piped to a file via shell redirection)
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(numeric_level)
    handlers.append(console)

    # Optional file handler — always JSON for machine parsing
    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(str(path), encoding="utf-8")
        file_handler.setLevel(numeric_level)
        handlers.append(file_handler)

    # Configure stdlib root logger (structlog routes through it)
    logging.basicConfig(
        format="%(message)s",
        level=numeric_level,
        handlers=handlers,
        force=True,
    )

    # Choose renderer: colorful console for TTYs, JSON for files/pipes
    if sys.stderr.isatty() and not log_file:
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Attach the formatter to all handlers
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )
    for h in handlers:
        h.setFormatter(formatter)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structured logger.

    Usage:
        log = get_logger()
        log.info("scan_started", tool="dup", included_dirs=["/home"])
    """
    return structlog.get_logger(name)
