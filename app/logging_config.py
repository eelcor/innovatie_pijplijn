"""Structuurde logging-configuratie voor de Innovatiepijplijn.

Ondersteunt twee modi:
  - CONSOLE (standaard): leesbare output voor lokaal gebruik
  - JSON: machine-readable logs voor log-aggregators (ELK, Loki, etc.)

Configureerbaar via omgevingsvariabelen:
  LOG_LEVEL    — logging level (DEBUG, INFO, WARNING, ERROR) — default: INFO
  LOG_FORMAT   — "console" of "json" — default: console
"""

import json
import logging
import logging.handlers
import os
import sys
from pathlib import Path
from datetime import datetime, timezone


def _default_log_record_factory(name):
    """Factory die een logrecord met process/hostname info teruggeeft."""
    record = logging.LogRecord(
        name=name, level=0, pathname="", lineno=0, msg="", args=None, exc_info=None,
    )
    return record


class JsonFormatter(logging.Formatter):
    """JSON-formatter voor machine-readable logs."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "process": getattr(record, "process", None),
        }

        if record.exc_info and record.exc_info[0]:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


class ConsoleFormatter(logging.Formatter):
    """Leesbare console-formatter met kleurondersteuning."""

    COLORS = {
        "DEBUG": "\033[36m",    # cyan
        "INFO": "\033[32m",     # green
        "WARNING": "\033[33m",  # yellow
        "ERROR": "\033[31m",    # red
        "CRITICAL": "\033[35m", # magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        level_color = self.COLORS.get(record.levelname, "")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"{level_color}[{timestamp}] {record.levelname:<8} {record.name}:{self.RESET} {record.getMessage()}"

        if record.exc_info and record.exc_info[0]:
            msg += f"\n{self.formatException(record.exc_info)}"

        return msg


def setup_logging():
    """Configureer logging voor de hele applicatie.

    Leest LOG_LEVEL en LOG_FORMAT uit omgevingsvariabelen.
    Schrijft naar console én logfile (data/app.log).
    """
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_format = os.environ.get("LOG_FORMAT", "console").lower()

    level = getattr(logging, log_level, logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Verwijder bestaande handlers (bijv. van uvicorn tests)
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    if log_format == "json":
        console_handler.setFormatter(JsonFormatter())
    else:
        console_handler.setFormatter(ConsoleFormatter())

    root_logger.addHandler(console_handler)

    # File handler — schrijft alles naar data/app.log (max 5MB, rotatie)
    try:
        import inspect
        # Bepaal project root vanaf deze module
        project_root = Path(inspect.getfile(setup_logging)).parent.parent
        log_dir = project_root / "data"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = str(log_dir / "app.log")

        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(ConsoleFormatter())  # leesbaar formaat voor admin UI
        root_logger.addHandler(file_handler)
    except Exception as e:
        # Logfile is optioneel — niet crashen bij falen
        pass

    # Verminder ruis van afhankelijke libraries
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("watchfiles").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    return level


# Setup bij import
setup_logging()

logger = logging.getLogger(__name__)
