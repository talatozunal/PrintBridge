# -*- coding: utf-8 -*-
"""Dönen dosya günlüğü + konsol."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from .config import Config


def setup_logging(config: Config, level: int = logging.INFO) -> None:
    config.log_dir.mkdir(parents=True, exist_ok=True)
    log_path = config.log_dir / "agent.log"

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    file_handler = RotatingFileHandler(
        log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    console = logging.StreamHandler(sys.stdout) if sys.stdout is not None else None
    if console is not None:
        console.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    # Yeniden yapılandırmada çift handler olmasın.
    for handler in list(root.handlers):
        root.removeHandler(handler)
    root.addHandler(file_handler)
    if console is not None:
        root.addHandler(console)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
