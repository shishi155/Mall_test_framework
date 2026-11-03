"""后台登录与权限用例（对应 Excel：MALL-ADM-SSO-*、MALL-ADM-AUTH-*）。"""
from __future__ import annotations

import allure
import pytest

from common import assertions as A
from common.http_client import HttpClient

pytestmark = [
    pytest.mark.smoke,
    allure.epic("mall 商城"),
    allure.feature("后台-登录与权限"),
]


@allure.story("登录认证")
@allure.title("正确账号密码登录成功，返回可用 JWT")
@pytest.mark.case_id("MALL-ADM-SSO-001")
def test_login_success(settings, admin_auth_api):
    acc = settings.admin_account
    with allure.step(f"使用内置管理员 {acc['username']} 登录"):
        resp = admin_auth_api.login(acc["username"], acc["password"])

    A.assert_success(resp)
    with allure.step("校验 token 结构"):
        data = A.assert_data_not_empty(resp)
        assert data.get("token"), f"token 为空：{resp}"
        assert data["token"].count(".") == 2, f"token 不是标准 JWT：{data['token'][:40]}"
        assert data.get("tokenHead") == "Bearer ", f"tokenHead 异常：{data.get('tokenHead')}"


@allure.story("登录认证")
@allure.title("密码错误时登录失败且不返回 token")
@pytest.mark.case_id("MALL-ADM-SSO-002")
def test_login_wrong_password(settings, admin_auth_api):
    acc = settings.admin_account
    resp = admin_auth_api.login(acc["username"], "Wrong@123456")
    # 实测：账号存在但密码错误 → code=500 "密码不正确"（与账号不存在时的 404 提示不同，见缺陷 D-05）
    A.assert_code(resp, 500)
    assert "密码不正确" in resp.message or "错误" in resp.message, f"提示异常：{resp.message!r}"
    assert resp.data is None, f"登录失败仍返回了数据：{resp.data}"


@allure.story("登录认证")
@allure.title("账号不存在与密码错误的提示应一致（防账号枚举）")
@pytest.mark.security
@pytest.mark.xfail(reason="已知缺陷 D-05：账号不存在返回 404「用户名或密码错误」，密码错误返回 500「密码不正确」，可枚举账号", strict=False)
@pytest.mark.case_id("MALL-ADM-SSO-003")
def test_login_user_not_exist_same_message(settings, admin_auth_api):
    wrong_pwd = admin_auth_api.login(settings.admin_account["username"], "Wrong@123456")
    not_exist = admin_auth_api.login("not_exist_9527", "Wrong@123456")

    with allure.step("两次失败的业务码与提示必须一致"):
        assert not_exist.code == wrong_pwd.code, (
            f"业务码不一致，可枚举账号：不存在={not_exist.code}，密码错误={wrong_pwd.code}"
        )
        assert not_exist.message == wrong_pwd.message, (
            f"提示不一致，可枚举账号：不存在={not_exist.message!r}，密码错误={wrong_pwd.message!r}"
        )


@allure.story("参数校验")
@allure.title("用户名为空时返回参数校验失败")
@pytest.mark.case_id("MALL-ADM-SSO-004")
def test_login_blank_username(admin_auth_api):
    resp = admin_auth_api.login("", "macro123")
    A.assert_code(resp, 404)
    assert "must not be empty" in resp.message or "不能为空" in resp.message, f"校验提示异常：{resp.message!r}"
    assert resp.data is None


@allure.story("权限认证")
@allure.title("未携带 token 访问受保护接口被拦截")
@pytest.mark.case_id("MALL-ADM-AUTH-001")
def test_admin_list_without_token(admin_anon):
    resp = admin_anon.get("/admin/list", params={"pageNum": 1, "pageSize": 5})
    A.assert_code(resp, 401, "暂未登录")
    assert not isinstance(resp.data, dict) or "list" not in (resp.data or {}), f"未登录却拿到了业务数据：{resp.data}"


@allure.story("权限认证")
@allure.title("伪造 JWT 访问受保护接口被拦截")
@pytest.mark.security
@pytest.mark.case_id("MALL-ADM-AUTH-002")
def test_admin_list_fake_token(settings):
    fake = HttpClient(settings.admin.base_url, settings.admin.timeout, "admin-fake").set_token("faketoken123")
    resp = fake.get("/admin/list", params={"pageNum": 1, "pageSize": 5})
    A.assert_code(resp, 401)
    assert "Exception" not in str(resp.body), "响应泄露了异常堆栈"


@allure.story("数据一致性")
@allure.title("后台商品列表 total 与数据库记录数一致")
@pytest.mark.regression
@pytest.mark.case_id("MALL-ADM-PRD-001")
def test_product_list_total_matches_db(admin_product_api, db):
    resp = admin_product_api.list(page_num=1, page_size=5)
    A.assert_success(resp)
    data = A.assert_data_not_empty(resp)

    with allure.step("与数据库 pms_product（未删除）记录数比对"):
        db_total = db.count("pms_product", "delete_status=0")
        assert data["total"] == db_total, f"接口 total={data['total']}，库中未删除商品数={db_total}"
        assert len(data["list"]) <= 5
        for item in data["list"]:
            assert item.get("id") and item.get("name"), f"商品字段缺失：{item}"
