import json
import logging
import random
from datetime import datetime


class JsonFormatter(logging.Formatter):
    """Minimal JSON formatter for production logs.

    - Merges base fields (time, level, name, message) with any attributes
      provided via `extra` on the log record (e.g., event, cart_id).
    - If the message is a dict, it is merged into the payload under its keys.
    - Dates are ISO-8601 UTC.
    """

    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        base = {
            "time": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "name": record.name,
        }

        # Start with message
        msg = record.getMessage()
        try:
            parsed = json.loads(msg) if isinstance(msg, str) else msg
        except Exception:
            parsed = msg

        if isinstance(parsed, dict):
            payload = {**base, **parsed}
        else:
            payload = {**base, "message": parsed}

        # Merge extra attributes from record.__dict__ (safe subset)
        for key, value in record.__dict__.items():
            if key in (
                "msg",
                "args",
                "levelname",
                "levelno",
                "name",
                "created",
                "msecs",
                "relativeCreated",
                "pathname",
                "filename",
                "module",
                "lineno",
                "funcName",
                "exc_info",
                "exc_text",
                "stack_info",
                "thread",
                "threadName",
                "processName",
                "process",
            ):
                continue
            # Only include simple JSON-serializable values
            try:
                json.dumps(value)
                payload.setdefault(key, value)
            except TypeError:
                payload.setdefault(key, str(value))

        return json.dumps(payload, ensure_ascii=False)


class SamplingFilter(logging.Filter):
    """Probabilistically drop logs to reduce noise while keeping signal.

    - `rate`: float in [0.0, 1.0]; fraction of matching records to allow.
    - `levels`: iterable of level names to which sampling applies (e.g., ["INFO"]).
    - `allow_events`: iterable of message strings that should never be sampled.

    Records with level not in `levels` are always allowed. If the record's
    `msg` is in `allow_events`, it is always allowed.
    """

    def __init__(self, rate: float = 1.0, levels: list[str] | None = None, allow_events: list[str] | None = None):
        super().__init__()
        try:
            self.rate = float(rate)
        except Exception:
            self.rate = 1.0
        self.levels = set(levels or ["INFO"])
        self.allow_events = set(allow_events or [])

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        # Always allow non-target levels
        if record.levelname not in self.levels:
            return True
        # Always allow explicit event names
        msg = getattr(record, "msg", "")
        if msg in self.allow_events:
            return True
        # Edge cases
        if self.rate >= 1.0:
            return True
        if self.rate <= 0.0:
            return False
        # Sample probabilistically
        try:
            return random.random() < self.rate
        except Exception:
            return True
