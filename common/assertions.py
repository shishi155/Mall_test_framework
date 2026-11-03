"""断言层：把「业务码 + 报文 + 数据结构」的校验统一收口。

约定：
- 商城接口 HTTP 状态码恒为 200，业务结果看 body.code（200 成功 / 401 / 403 / 404 / 500）；
- 断言失败时把完整响应带进报错信息，Allure 里一眼能看到实际值。
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from common.http_client import ApiResponse


def _ctx(resp: ApiResponse) -> str:
    return f"[{resp.method} {resp.url}] HTTP={resp.status_code} code={resp.code} message={resp.message!r} body={resp.text()[:600]}"


def assert_code(resp: ApiResponse, expected: int, msg_contains: str | None = None) -> ApiResponse:
    assert resp.code == expected, f"业务码不符，期望 code={expected}，实际 {_ctx(resp)}"
    if msg_contains:
        assert msg_contains in resp.message, f"message 不含 {msg_contains!r}，实际 {resp.message!r} | {_ctx(resp)}"
    return resp


def assert_success(resp: ApiResponse, msg_contains: str | None = None) -> ApiResponse:
    """业务成功（code=200）。"""
    return assert_code(resp, 200, msg_contains)


def assert_failed(resp: ApiResponse, expected_codes: Iterable[int] = (401, 403, 404, 500)) -> ApiResponse:
    """业务失败：code 在允许集合内且不为 200。"""
    assert resp.code in set(expected_codes), f"期望业务失败（{list(expected_codes)}），实际 {_ctx(resp)}"
    return resp


def assert_no_sensitive_leak(resp: ApiResponse, keywords: Iterable[str] = ("password", "secret", "token\":\"ey")) -> None:
    """响应体不得回显敏感字段（用于登录/查询类接口的安全校验）。"""
    text = resp.text().lower()
    for kw in keywords:
        assert kw.lower() not in text, f"响应疑似泄露敏感信息 {kw!r} | {_ctx(resp)}"


def assert_data_not_empty(resp: ApiResponse, path: str | None = None) -> Any:
    """data 非空（支持 obj.a.b 形式的路径）。"""
    data = resp.data
    if path:
        for seg in path.split("."):
            data = data.get(seg) if isinstance(data, Mapping) else None
    assert data, f"data{'(' + path + ')' if path else ''} 不应为空 | {_ctx(resp)}"
    return data


def assert_field(obj: Mapping[str, Any], field: str, expected: Any) -> None:
    assert isinstance(obj, Mapping), f"待校验对象不是字典：{type(obj)}"
    actual = obj.get(field)
    assert actual == expected, f"字段 {field} 期望 {expected!r}，实际 {actual!r}，对象={obj}"


def assert_fields(obj: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
    """批量校验：不存在的字段会报出具体字段名。"""
    missing = [k for k in expected if k not in obj]
    assert not missing, f"响应缺少字段 {missing}，实际字段={list(obj.keys())}"
    for k, v in expected.items():
        assert obj[k] == v, f"字段 {k} 期望 {v!r}，实际 {obj[k]!r}"


def assert_db_equal(actual: Any, expected: Any, desc: str = "") -> None:
    assert actual == expected, f"数据一致性校验失败 {desc}：库中={actual!r}，期望={expected!r}"
