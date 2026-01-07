import json
import logging
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

UTC = timezone.utc
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


class StructuredLogger:
    def __init__(self, name: str, logfile: str | None = None):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

        # Clear old handlers (VERY important for reloads)
        self.logger.handlers.clear()

        formatter = logging.Formatter("%(message)s")

        # 1️⃣ STDOUT handler (Docker-friendly)
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(formatter)
        self.logger.addHandler(stdout_handler)

        # 2️⃣ File handler (optional)
        if logfile:
            file_handler = RotatingFileHandler(
                LOG_DIR / logfile,
                maxBytes=10 * 1024 * 1024,  # 10 MB
                backupCount=5,              # keep last 5 files
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def log(self, *, event: str, **fields):
        payload = {
            "event": event,
            "timestamp": datetime.now(UTC).isoformat(),
            **{k: v for k, v in fields.items() if v is not None},
        }

        self.logger.info(json.dumps(payload, default=str))
