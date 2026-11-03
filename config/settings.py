"""配置加载：yaml + 环境变量覆盖。

优先级：环境变量 > config.yaml > 默认值
环境变量表：
  MALL_ENV          运行环境名（local / ci）
  MALL_ADMIN_URL    后台接口地址
  MALL_PORTAL_URL   前台接口地址
  MALL_WEB_URL      后台前端地址
  MALL_DB_HOST / MALL_DB_PORT / MALL_DB_USER / MALL_DB_PASSWORD / MALL_DB_NAME
  MALL_ADMIN_USER / MALL_ADMIN_PASSWORD
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = Path(__file__).resolve().parent / "config.yaml"


@dataclass
class ServiceConfig:
    base_url: str
    timeout: int = 10


@dataclass
class DbConfig:
    host: str
    port: int
    user: str
    password: str
    database: str
    charset: str = "utf8mb4"


@dataclass
class Settings:
    env: str
    name: str
    admin: ServiceConfig
    portal: ServiceConfig
    web: ServiceConfig
    db: DbConfig
    accounts: Dict[str, Dict[str, str]] = field(default_factory=dict)
    case_file: Path = ROOT / "testcases" / "mall_测试用例_v1.1.xlsx"
    report_dir: Path = ROOT / "reports"

    # ---------- 便捷访问 ----------
    @property
    def admin_account(self) -> Dict[str, str]:
        return self.accounts.get("admin", {})

    def url(self, service: str) -> str:
        return getattr(self, service).base_url

    def allure_results_dir(self) -> Path:
        d = self.report_dir / "allure-results"
        d.mkdir(parents=True, exist_ok=True)
        return d


def _env(key: str, default: Any = None) -> Any:
    v = os.environ.get(key)
    return v if v not in (None, "") else default


def load_settings(env: str | None = None) -> Settings:
    raw = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8"))
    env_name = env or _env("MALL_ENV", raw.get("default_env", "local"))
    if env_name not in raw["envs"]:
        raise ValueError(f"未知环境 {env_name}，可选：{list(raw['envs'])}")
    c = raw["envs"][env_name]

    admin = ServiceConfig(_env("MALL_ADMIN_URL", c["admin"]["base_url"]), int(_env("MALL_ADMIN_TIMEOUT", c["admin"].get("timeout", 10))))
    portal = ServiceConfig(_env("MALL_PORTAL_URL", c["portal"]["base_url"]), int(_env("MALL_PORTAL_TIMEOUT", c["portal"].get("timeout", 10))))
    web = ServiceConfig(_env("MALL_WEB_URL", c["web"]["base_url"]), int(c["web"].get("timeout", 10)))

    db_raw = c["db"]
    db = DbConfig(
        host=_env("MALL_DB_HOST", db_raw["host"]),
        port=int(_env("MALL_DB_PORT", db_raw["port"])),
        user=_env("MALL_DB_USER", db_raw["user"]),
        password=_env("MALL_DB_PASSWORD", db_raw["password"]),
        database=_env("MALL_DB_NAME", db_raw["database"]),
        charset=db_raw.get("charset", "utf8mb4"),
    )

    accounts = {
        "admin": {
            "username": _env("MALL_ADMIN_USER", c["accounts"]["admin"]["username"]),
            "password": _env("MALL_ADMIN_PASSWORD", c["accounts"]["admin"]["password"]),
        }
    }

    return Settings(env=env_name, name=c["name"], admin=admin, portal=portal, web=web, db=db, accounts=accounts)
