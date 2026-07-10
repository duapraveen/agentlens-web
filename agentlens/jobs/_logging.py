"""Structured logging for batch jobs: JSON lines to stdout and to the jobs log file.

Never log transcript content — call IDs and metadata only (constitution V.3).
"""

import logging
from pathlib import Path

import structlog


def configure_job_logging(log_path: Path) -> structlog.stdlib.BoundLogger:
    """Configure structlog to emit JSON lines to stdout and append to log_path."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(log_path)],
        force=True,
    )
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso", key="ts"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )
    logger: structlog.stdlib.BoundLogger = structlog.get_logger("agentlens.jobs")
    return logger
