"""HTTP 客户端：统一会话、鉴权、耗时统计、Allure 附件、日志。

设计要点：
- 每个服务一个实例（admin/portal），互不干扰；
- 业务错误（code != 200）不抛异常，由断言层负责判定，便于逆向用例；
- 每一步请求/响应都写入 Allure 附件与日志，失败可回溯。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import requests

from common.logger import get_logger

try:  # Allure 可选依赖，脱离 allure-pytest 也能运行
    import allure
except Exception:  # pragma: no cover
    allure = None

log = get_logger("http")


@dataclass
class ApiResponse:
    """统一的响应对象。"""
    status_code: int
    body: Any
    elapsed_ms: float
    method: str
    url: str
    request_body: Any = None
    headers: Dict[str, str] = field(default_factory=dict)

    # ---- 商城业务字段 ----
    @property
    def code(self) -> Any:
        return self.body.get("code") if isinstance(self.body, dict) else None

    @property
    def message(self) -> str:
        return (self.body.get("message") or "") if isinstance(self.body, dict) else ""

    @property
    def data(self) -> Any:
        return self.body.get("data") if isinstance(self.body, dict) else None

    def __repr__(self) -> str:
        return f"<ApiResponse {self.method} {self.url} HTTP{self.status_code} code={self.code} {self.elapsed_ms:.0f}ms>"

    def text(self) -> str:
        return json.dumps(self.body, ensure_ascii=False) if not isinstance(self.body, str) else self.body


class HttpClient:
    def __init__(self, base_url: str, timeout: int = 10, name: str = "api"):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.name = name
        self.session = requests.Session()
        self.token: Optional[str] = None
        self.default_headers = {"Accept": "application/json"}

    # ---------- 鉴权 ----------
    def set_token(self, token: Optional[str]) -> "HttpClient":
        self.token = token
        return self

    def _headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        h = dict(self.default_headers)
        if self.token:
            h["Authorization"] = self.token if self.token.lower().startswith("bearer ") else f"Bearer {self.token}"
        if extra:
            h.update(extra)
        return h

    # ---------- 请求 ----------
    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Any = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        files: Any = None,
    ) -> ApiResponse:
        url = f"{self.base_url}{path}"
        method = method.upper()
        merged_headers = self._headers(headers)

        req_desc = {
            "service": self.name,
            "method": method,
            "url": url,
            "params": params,
            "json": json_body,
            "data": data,
            "headers": {k: v for k, v in merged_headers.items() if k.lower() != "authorization"},
            "auth": bool(self.token),
        }
        log.info("→ %s %s params=%s json=%s", method, url, params, json_body)

        started = time.perf_counter()
        resp = self.session.request(
            method, url, params=params, json=json_body, data=data,
            headers=merged_headers, files=files, timeout=self.timeout,
        )
        elapsed = (time.perf_counter() - started) * 1000

        try:
            body = resp.json()
        except ValueError:
            body = resp.text

        result = ApiResponse(resp.status_code, body, elapsed, method, url, json_body or data,
                               headers=dict(resp.headers))
        log.info("← %s %s HTTP%s code=%s %0.0fms", method, url, resp.status_code, result.code, elapsed)

        self._attach(req_desc, result)
        return result

    # ---------- 语法糖 ----------
    def get(self, path: str, **kw) -> ApiResponse:
        return self.request("GET", path, **kw)

    def post(self, path: str, **kw) -> ApiResponse:
        return self.request("POST", path, **kw)

    def put(self, path: str, **kw) -> ApiResponse:
        return self.request("PUT", path, **kw)

    def delete(self, path: str, **kw) -> ApiResponse:
        return self.request("DELETE", path, **kw)

    # ---------- Allure ----------
    @staticmethod
    def _attach(req_desc: Dict[str, Any], result: ApiResponse) -> None:
        if allure is None:
            return
        try:
            allure.attach(
                json.dumps(req_desc, ensure_ascii=False, indent=2),
                name=f"请求 {req_desc['method']} {req_desc['url']}",
                attachment_type=allure.attachment_type.JSON,
            )
            allure.attach(
                json.dumps(
                    {
                        "http_status": result.status_code,
                        "elapsed_ms": round(result.elapsed_ms, 1),
                        "body": result.body,
                    },
                    ensure_ascii=False, indent=2,
                ),
                name=f"响应 {result.status_code} / code={result.code}",
                attachment_type=allure.attachment_type.JSON,
            )
        except Exception:  # pragma: no cover
            pass
