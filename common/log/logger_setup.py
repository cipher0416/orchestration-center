from loguru import logger
from pathlib import Path

_LOG_DIR = Path("logs")
_LOG_DIR.mkdir(exist_ok=True)

LOG_FORMAT = "{time:YYYY-MM-DD HH:mm:ss} - {name} - {level} - {message}"


def add_module_logger(module_prefix: str):
    logger.add(
        _LOG_DIR / f"{module_prefix}_{{time:YYYY-MM-DD}}.log",
        format=LOG_FORMAT,
        level="INFO",
        rotation="1 day",
        retention="30 days",
        compression="zip",
        encoding="utf-8"
    )
