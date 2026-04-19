"""Cost tracking: append-only JSONL log of API costs."""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.config import COST_LOG_PATH

logger = logging.getLogger(__name__)

_log_path = Path(COST_LOG_PATH)
_lock = threading.Lock()


def log_cost(service: str, units: float, cost_usd: float, meta: dict | None = None) -> None:
    """Append a cost entry to costs.jsonl."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": service,
        "units": units,
        "cost_usd": round(cost_usd, 6),
    }
    if meta:
        entry["meta"] = meta
    with _lock:
        with _log_path.open("a") as f:
            f.write(json.dumps(entry) + "\n")
    logger.debug("Cost logged: %s $%.6f", service, cost_usd)


def total_cost() -> float:
    """Sum all costs from the log file."""
    with _lock:
        if not _log_path.exists():
            return 0.0
        total = 0.0
        for line in _log_path.read_text().strip().split("\n"):
            if line:
                total += json.loads(line).get("cost_usd", 0.0)
    return total
