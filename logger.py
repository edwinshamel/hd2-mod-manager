import logging
import sys
from pathlib import Path
from datetime import datetime

APP_DIR = Path.home() / "hd2-mod-manager"
LOGS_DIR = APP_DIR / "logs"

_loggers: dict[str, logging.Logger] = {}


def _get_logger(level_name: str) -> logging.Logger:
    if level_name in _loggers:
        return _loggers[level_name]

    level_dir = LOGS_DIR / level_name
    level_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    log_file = level_dir / f"{today}.log"

    logger = logging.getLogger(f"hd2mm.{level_name}")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # Evitar duplicar handlers si se llama varias veces
    if not logger.handlers:
        fmt = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Handler al archivo
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

        # Handler a consola
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(fmt)
        logger.addHandler(ch)

    _loggers[level_name] = logger
    return logger


def info(message: str):
    """Registra un mensaje informativo."""
    _get_logger("info").info(message)


def debug(message: str):
    """Registra un mensaje de depuración."""
    _get_logger("debug").debug(message)


def error(message: str, exc: Exception = None):
    """Registra un mensaje de error. Opcionalmente incluye la excepción."""
    logger = _get_logger("error")
    if exc:
        logger.error(f"{message} | Excepción: {type(exc).__name__}: {exc}", exc_info=exc)
    else:
        logger.error(message)
