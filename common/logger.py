"""日志：控制台 + 文件，UTF-8，供用例与请求层复用。"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "reports" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

_CONFIGURED = False


def get_logger(name: str = "mall") -> logging.Logger:
    global _CONFIGURED
    if not _CONFIGURED:
        fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s", "%Y-%m-%d %H:%M:%S"
        )
        root = logging.getLogger("mall")
        root.setLevel(logging.INFO)
        root.propagate = False

        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        root.addHandler(sh)

        fh = logging.FileHandler(LOG_DIR / "run.log", encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
        _CONFIGURED = True
    return logging.getLogger(f"mall.{name}" if name != "mall" else "mall")
