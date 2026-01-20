"""
Structured logging configuration
"""
import structlog
import logging
import sys


def setup_logging():
    """Configure structured logging for production"""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO
    )

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()  # JSON for production
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger()


# Global logger instance
logger = setup_logging()
