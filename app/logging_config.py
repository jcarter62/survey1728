import logging
import contextvars

# Context variables populated per-request by middleware
request_client_ip: contextvars.ContextVar[str] = contextvars.ContextVar("request_client_ip", default="-")
request_member_name: contextvars.ContextVar[str] = contextvars.ContextVar("request_member_name", default="-")
request_member_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_member_id", default="-")


class RequestContextFormatter(logging.Formatter):
    """Formatter that injects request-scoped fields into LogRecord if missing."""
    
    def format(self, record: logging.LogRecord) -> str:
        # Ensure fields exist in the record before formatting
        if not hasattr(record, "client_ip"):
            record.client_ip = request_client_ip.get()
        if not hasattr(record, "member_name"):
            record.member_name = request_member_name.get()
        if not hasattr(record, "member_id"):
            record.member_id = request_member_id.get()
        return super().format(record)


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root and uvicorn loggers to include request context fields.

    We use a custom Formatter to inject the context fields (client_ip, member_id, member_name)
    into the LogRecord if they are missing. This avoids KeyErrors when using these fields
    in the format string.
    """
    fmt = "%(asctime)s %(levelname)s [%(client_ip)s] [member:%(member_id)s %(member_name)s] %(name)s: %(message)s"
    formatter = RequestContextFormatter(fmt)
    
    root = logging.getLogger()
    
    # If root has handlers (e.g. from uvicorn/gunicorn config), patch them.
    # Otherwise add a default StreamHandler.
    if root.handlers:
        for h in root.handlers:
            h.setFormatter(formatter)
    else:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        root.addHandler(handler)

    root.setLevel(level)
    
    # Ensure uvicorn/gunicorn loggers also get the formatter
    for lname in ("uvicorn", "uvicorn.error", "uvicorn.access", "gunicorn.error", "gunicorn.access"):
        log = logging.getLogger(lname)
        for h in log.handlers:
            h.setFormatter(formatter)

    # Suppress uvicorn.access logs to avoid duplicates/empty context logs
    # The application middleware handles access logging with full context.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


__all__ = [
    "request_client_ip",
    "request_member_name",
    "request_member_id",
    "RequestContextFormatter",
    "setup_logging",
]
