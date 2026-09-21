from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path


def _preferred_log_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return base / "OrangeGadgets" / "pdf2wordx" / "pdf2wordx.log"


def _file_handler() -> logging.Handler:
    paths = (
        _preferred_log_path(),
        Path(tempfile.gettempdir()) / "OrangeGadgets" / "pdf2wordx.log",
    )
    for path in paths:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            return logging.FileHandler(path, encoding="utf-8")
        except OSError:
            continue
    return logging.NullHandler()


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    handler = _file_handler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger
