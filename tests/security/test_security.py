"""安全专项（MALL-SEC-*）：认证绕过、越权、注入、信息泄露、防护缺失。

约定：断言的是「安全正确行为」，当前系统不满足的用 xfail 并关联缺陷编号。
"""
from __future__ import annotations

import base64
import json

import allure
import pytest

from common import assertions as A
from common import data_factory
from common.http_client import HttpClient

pytestmark = [
    pytest.mark.security,
    allure.epic("mall 商城"),
    allure.feature("安全专项"),
]


# ---------------- 认证与鉴权 ----------------
@allure.story("认证")
@allure.title("后台注册接口不应允许未登录调用")
@pytest.mark.xfail(reason="已知缺陷 D-15：/admin/register 在安全白名单中，任意人可注册后台账号", strict=False)
@pytest.mark.case_id("MALL-SEC-001")
def test_admin_register_requires_auth(admin_anon):
    acc = {"username": data_factory.unique_username("sec_"), "password": "Test@1234", "nickName": "sec"}
    resp = admin_anon.post("/admin/register", json_body=acc)
    assert resp.code in (401, 403), f"未登录即可注册后台账号：{resp}"


@allure.story("认证")
@allure.title("前台 token 不能访问后台接口")
@pytest.mark.case_id("MALL-SEC-002")
def test_portal_token_rejected_by_admin(settings, portal_member):
    client = HttpClient(settings.admin.base_url, settings.admin.timeout, "x").set_token(portal_member["token"])
    resp = client.get("/admin/list", params={"pageNum": 1, "pageSize": 5})
    A.assert_code(resp, 401)


@allure.story("认证")
@allure.title("篡改 JWT 载荷后访问被拒绝")
@pytest.mark.case_id("MALL-SEC-003")
def test_tampered_jwt(settings, admin_token):
    header, payload, sign = admin_token.split(".")
    raw = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    raw["sub"] = "admin_hacked"
    forged_payload = base64.urlsafe_b64encode(json.dumps(raw).encode()).decode().rstrip("=")
    forged = f"{header}.{forged_payload}.{sign}"

    client = HttpClient(settings.admin.base_url, settings.admin.timeout, "x").set_token(forged)
    resp = client.get("/admin/list", params={"pageNum": 1, "pageSize": 5})
    A.assert_code(resp, 401)


@allure.story("认证")
@allure.title("缺少 Bearer 前缀的 token 被拒绝")
@pytest.mark.case_id("MALL-SEC-004")
def test_token_without_bearer(settings, admin_token):
    client = HttpClient(settings.admin.base_url, settings.admin.timeout, "x")
    client.token = None
    resp = client.get("/admin/list", params={"pageNum": 1, "pageSize": 5},
                      headers={"Authorization": admin_token})
    A.assert_code(resp, 401)


@allure.story("鉴权")
@allure.title("后台关键接口在未登录时全部拒绝")
@pytest.mark.case_id("MALL-SEC-005")
def test_admin_endpoints_require_auth(admin_anon):
    paths = [
        ("GET", "/admin/list"), ("GET", "/product/list"), ("GET", "/order/list"),
        ("GET", "/role/list"), ("GET", "/coupon/list"), ("GET", "/memberLevel/list"),
    ]
    for method, path in paths:
        resp = admin_anon.request(method, path, params={"pageNum": 1, "pageSize": 1})
        assert resp.code == 401, f"{method} {path} 未登录却未被拦截：{resp}"


# ---------------- 注入 ----------------
@allure.story("注入")
@allure.title("登录用户名 SQL 注入不生效且不泄露 SQL 错误")
@pytest.mark.case_id("MALL-SEC-006")
def test_login_sql_injection(admin_anon):
    resp = admin_anon.post("/admin/login", json_body={"username": "admin' OR '1'='1", "password": "x"})
    assert resp.code != 200, f"SQL 注入疑似绕过登录：{resp}"
    assert "SQL" not in str(resp.body) and "syntax" not in str(resp.body), f"响应泄露 SQL 错误：{resp.body}"


@allure.story("注入")
@allure.title("搜索参数 SQL 注入不生效")
@pytest.mark.case_id("MALL-SEC-007")
def test_search_sql_injection(portal_client):
    resp = portal_client.get("/product/search",
                             params={"keyword": "1' AND (SELECT 1 FROM (SELECT SLEEP(2))x) AND '1'='1",
                                     "pageNum": 1, "pageSize": 5})
    A.assert_success(resp)
    assert resp.elapsed_ms < 2000, f"疑似发生 SQL 注入（响应耗时 {resp.elapsed_ms:.0f}ms）"


# ---------------- 信息泄露 ----------------
@allure.story("信息泄露")
@allure.title("登录失败响应不包含堆栈信息")
@pytest.mark.case_id("MALL-SEC-008")
def test_error_no_stacktrace(admin_anon):
    resp = admin_anon.post("/admin/login", json_body={"username": "not_exist", "password": "x"})
    body = str(resp.body).lower()
    for kw in ("exception", "at com.macro", "stacktrace", "java.lang"):
        assert kw not in body, f"错误响应泄露技术细节 {kw}：{resp.body}"


@allure.story("信息泄露")
@allure.title("Actuator 敏感端点不应匿名暴露")
@pytest.mark.case_id("MALL-SEC-009")
def test_actuator_not_exposed(admin_anon):
    for path in ("/actuator/env", "/actuator/beans", "/actuator/configprops"):
        resp = admin_anon.get(path)
        assert resp.status_code != 200 or resp.code in (401, 403), f"敏感端点匿名可访问：{path} -> {resp.status_code}"


@allure.story("信息泄露")
@allure.title("Druid 监控页需登录后访问")
@pytest.mark.case_id("MALL-SEC-010")
def test_druid_protected(admin_anon):
    resp = admin_anon.get("/druid/index.html")
    assert resp.status_code < 500, f"响应异常：{resp.status_code}"
    if resp.status_code == 200 and "druid" in str(resp.body).lower():
        assert "login" in str(resp.body).lower() or "登录" in str(resp.body), "Druid 监控页匿名可访问"


@allure.story("信息泄露")
@allure.title("用户信息接口不返回密码字段")
@pytest.mark.case_id("MALL-SEC-011")
def test_admin_info_no_password(admin_client):
    resp = admin_client.get("/admin/info")
    A.assert_success(resp)
    assert "password" not in json.dumps(resp.data, ensure_ascii=False), f"用户信息返回了密码：{resp.data}"


@allure.story("信息泄露")
@allure.title("支付/订单异常响应不泄露 SQL 语句")
@pytest.mark.xfail(reason="已知缺陷 D-14：空购物车下单把 MySQL 语法错误原文返回前端", strict=False)
@pytest.mark.case_id("MALL-SEC-012")
def test_sql_error_not_leaked(shopper):
    resp = shopper.order.generate_order({
        "memberReceiveAddressId": shopper.address_id, "couponId": None,
        "useIntegration": 0, "payType": 0, "cartIds": [],
    })
    assert "SQL" not in str(resp.body), f"泄露 SQL 错误：{resp.body}"


# ---------------- 防护缺失 ----------------
@allure.story("防护")
@allure.title("后台登录连续失败应触发锁定或验证码")
@pytest.mark.xfail(reason="已知缺陷 D-16：后台登录无失败次数限制，可被暴力破解", strict=False)
@pytest.mark.case_id("MALL-SEC-013")
def test_login_bruteforce_protection(admin_anon, settings):
    acc = settings.admin_account
    codes = []
    for _ in range(6):
        resp = admin_anon.post("/admin/login", json_body={"username": acc["username"], "password": "Wrong@123"})
        codes.append(resp.code)
    assert any(c != 500 for c in codes[3:]), f"连续失败 6 次仍无任何防护：{codes}"


@allure.story("防护")
@allure.title("异常大的请求体不应导致服务端 5xx")
@pytest.mark.case_id("MALL-SEC-014")
def test_large_payload(admin_anon):
    resp = admin_anon.post("/admin/login", json_body={
        "username": "a" * 200000, "password": "b" * 200000,
    })
    assert resp.status_code < 500 or resp.code != 500, f"超大请求体导致服务端异常：HTTP {resp.status_code} code={resp.code}"


@allure.story("防护")
@allure.title("不支持的 HTTP 方法被拒绝")
@pytest.mark.case_id("MALL-SEC-015")
def test_http_method_not_allowed(admin_anon):
    resp = admin_anon.request("PUT", "/admin/login", json_body={"username": "a", "password": "b"})
    assert resp.status_code in (200, 401, 405), f"方法篡改返回异常状态：{resp.status_code}"
    assert resp.code != 200, f"PUT 方法竟然登录成功：{resp}"


@allure.story("防护")
@allure.title("跨域响应头不应无条件放行任意来源")
@pytest.mark.xfail(reason="已知缺陷 D-17：GlobalCorsConfig 使用 allowedOriginPatterns(*)，任意来源可跨域读取响应（中风险）", strict=False)
@pytest.mark.case_id("MALL-SEC-016")
def test_cors_policy(admin_anon):
    resp = admin_anon.request("GET", "/admin/login", headers={"Origin": "https://evil.example.com"})
    allow = resp.headers.get("Access-Control-Allow-Origin")
    if allow is not None:
        assert allow != "*" and "evil.example.com" not in allow, f"CORS 放行了任意来源：{allow}"
