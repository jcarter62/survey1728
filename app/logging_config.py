import logging
import contextvars

# Context variables populated per-request by middleware
request_client_ip: contextvars.ContextVar[str] = contextvars.ContextVar("request_client_ip", default="-")
request_member_name: contextvars.ContextVar[str] = contextvars.ContextVar("request_member_name", default="-")
request_member_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_member_id", default="-")


class RequestContextFilter(logging.Filter):
    """Logging filter that injects request-scoped fields into LogRecord.

    Ensure this filter is attached to loggers/handlers so formatters can
    use %(client_ip)s, %(member_id)s and %(member_name)s in log formats.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Provide default values if not set in context
        try:
            record.client_ip = request_client_ip.get()
        except LookupError:
            record.client_ip = "-"
        try:
            record.member_name = request_member_name.get()
        except LookupError:
            record.member_name = "-"
        try:
            record.member_id = request_member_id.get()
        except LookupError:
            record.member_id = "-"
        return True


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root and uvicorn loggers to include request context fields.

    This config is intentionally minimal: we add the RequestContextFilter to
    the root logger and uvicorn loggers so `%(client_ip)s`, `%(member_id)s` and
    `%(member_name)s` are available to formatters. We don't override uvicorn's
    handlers deeply to avoid clobbering their behavior.
    """
    fmt = "%(asctime)s %(levelname)s [%(client_ip)s] [member:%(member_id)s %(member_name)s] %(name)s: %(message)s"
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt))
    handler.addFilter(RequestContextFilter())

    root = logging.getLogger()
    # Avoid adding duplicate handlers if setup_logging called multiple times
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        root.addHandler(handler)
    root.setLevel(level)
    # Ensure uvicorn loggers also get the filter so their records have the fields
    for lname in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        log = logging.getLogger(lname)
        log.addFilter(RequestContextFilter())


__all__ = [
    "request_client_ip",
    "request_member_name",
    "request_member_id",
    "RequestContextFilter",
    "setup_logging",
]
