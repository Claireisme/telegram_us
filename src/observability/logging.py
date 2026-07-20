from __future__ import annotations

import logging
import sys
from collections.abc import Callable

from src.config.settings import Settings


def configure_logging(name: str, settings: Settings) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger

    settings.log_path.parent.mkdir(parents=True, exist_ok=True)
    settings.error_log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)sZ %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    formatter.converter = time_gmt

    info_handler = logging.FileHandler(settings.log_path, encoding="utf-8")
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(formatter)

    error_handler = logging.FileHandler(settings.error_log_path, encoding="utf-8")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    logger.addHandler(info_handler)
    logger.addHandler(error_handler)
    return logger


def run_with_logging(script_name: str, func: Callable[[], None]) -> None:
    settings = Settings.load()
    logger = configure_logging(script_name, settings)
    logger.info("start argv=%s", " ".join(sys.argv[1:]))
    try:
        func()
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        if code == 0:
            logger.info("complete")
        else:
            logger.error("system exit code=%s", exc.code)
        raise
    except Exception:
        logger.exception("failed")
        raise
    else:
        logger.info("complete")


def time_gmt(*args):
    import time

    return time.gmtime(*args)
