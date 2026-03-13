import contextvars
import logging
import logging.config
from contextvars import Token
from typing import override


_correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id",
    default="-",
)


class CorrelationIdFilter(logging.Filter):
    @override
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = _correlation_id.get()
        return True


def set_correlation_id(correlation_id: str) -> Token[str]:
    return _correlation_id.set(correlation_id)


def reset_correlation_id(token: Token[str]) -> None:
    _correlation_id.reset(token)


def configure_logging(log_level: str) -> None:
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "correlation_id": {
                    "()": "src.logging_config.CorrelationIdFilter",
                }
            },
            "formatters": {
                "json": {
                    "()": "pythonjsonlogger.json.JsonFormatter",
                    "format": "%(asctime)s %(levelname)s %(name)s %(message)s %(correlation_id)s",
                    "rename_fields": {
                        "asctime": "timestamp",
                        "levelname": "level",
                    },
                    "defaults": {
                        "correlation_id": "-",
                    },
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                    "filters": ["correlation_id"],
                    "stream": "ext://sys.stdout",
                }
            },
            "root": {
                "level": log_level,
                "handlers": ["console"],
            },
        }
    )
