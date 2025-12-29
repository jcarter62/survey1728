import logging
import contextvars
import sys

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
    """Configure logging to include request context and output to stdout.

    This setup:
    1. Configures the root logger to write to sys.stdout using our custom formatter.
    2. Aggressively silences 'uvicorn.access' to avoid duplicate/standard access logs.
    3. Configures 'uvicorn.error' and others to use our formatter and handler.
    """
    fmt = "%(asctime)s %(levelname)s [%(client_ip)s] [member:%(member_id)s %(member_name)s] %(name)s: %(message)s"
    formatter = RequestContextFormatter(fmt)
    
    # Create a handler that writes to stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Configure root logger
    root = logging.getLogger()
    root.setLevel(level)
    # Remove existing handlers and add ours
    if root.handlers:
        for h in list(root.handlers):
            root.removeHandler(h)
    root.addHandler(handler)

    # Silence uvicorn.access logger
    # We handle access logging in the application middleware with full context.
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.handlers = []
    uvicorn_access.propagate = False
    uvicorn_access.setLevel(logging.CRITICAL)
    uvicorn_access.disabled = True

    # Configure other uvicorn/gunicorn loggers to use our handler
    # This ensures they use the correct format and output stream
    for lname in ("uvicorn", "uvicorn.error", "gunicorn.error"):
        log = logging.getLogger(lname)
        log.handlers = []
        log.propagate = False # Do not propagate to root (we handle it here)
        log.addHandler(handler)
        log.setLevel(level)


__all__ = [
    "request_client_ip",
    "request_member_name",
    "request_member_id",
    "RequestContextFormatter",
    "setup_logging",
]
