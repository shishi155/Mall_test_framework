"""数据库访问：用于「接口 + DB 双向校验」类用例。

用法：
    with DB(settings.db) as db:
        assert db.count("pms_product") > 0
        row = db.query_one("select id, stock from pms_sku_stock where id=%s", (sku_id,))
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional, Sequence

import pymysql

from config.settings import DbConfig
from common.logger import get_logger

log = get_logger("db")


class DB:
    def __init__(self, cfg: DbConfig):
        self.cfg = cfg
        self.conn: Optional[pymysql.connections.Connection] = None

    # ---------- 连接管理 ----------
    def connect(self) -> "DB":
        if self.conn is None:
            self.conn = pymysql.connect(
                host=self.cfg.host, port=self.cfg.port, user=self.cfg.user,
                password=self.cfg.password, database=self.cfg.database,
                charset=self.cfg.charset, autocommit=True, cursorclass=pymysql.cursors.DictCursor,
            )
            log.info("DB connected %s:%s/%s", self.cfg.host, self.cfg.port, self.cfg.database)
        return self

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self) -> "DB":
        return self.connect()

    def __exit__(self, *exc) -> None:
        self.close()

    # ---------- 查询 ----------
    def query_all(self, sql: str, args: Sequence[Any] | None = None) -> List[Dict[str, Any]]:
        self.connect()
        with self.conn.cursor() as cur:
            cur.execute(sql, args or ())
            return list(cur.fetchall())

    def query_one(self, sql: str, args: Sequence[Any] | None = None) -> Optional[Dict[str, Any]]:
        rows = self.query_all(sql, args)
        return rows[0] if rows else None

    def scalar(self, sql: str, args: Sequence[Any] | None = None) -> Any:
        row = self.query_one(sql, args)
        return list(row.values())[0] if row else None

    def count(self, table: str, where: str = "", args: Sequence[Any] | None = None) -> int:
        sql = f"select count(*) as cnt from {table}" + (f" where {where}" if where else "")
        return int(self.scalar(sql, args) or 0)

    # ---------- 写入（仅测试数据准备/清理使用） ----------
    def execute(self, sql: str, args: Sequence[Any] | None = None) -> int:
        self.connect()
        with self.conn.cursor() as cur:
            return cur.execute(sql, args or ())


@contextmanager
def db_session(cfg: DbConfig):
    db = DB(cfg)
    try:
        yield db.connect()
    finally:
        db.close()
