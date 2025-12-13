import logging
try:
    import structlog
except Exception:
    structlog = None

def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO)
    if structlog:
        structlog.configure(
            processors=[
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.add_log_level,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
            cache_logger_on_first_use=True,
        )

logger = structlog.get_logger() if structlog else logging.getLogger("app")
