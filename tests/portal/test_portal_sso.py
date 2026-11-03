"""前台注册登录用例（对应 Excel：MALL-POR-SSO-*）。"""
from __future__ import annotations

import allure
import pytest

from common import assertions as A
from common import data_factory

pytestmark = [
    pytest.mark.smoke,
    allure.epic("mall 商城"),
    allure.feature("前台-注册登录"),
]


@allure.story("注册")
@allure.title("新手机号完成注册，密码以 BCrypt 入库")
@pytest.mark.case_id("MALL-POR-SSO-001")
def test_register_success(portal_sso_api, db):
    acc = data_factory.member_account()
    with allure.step(f"手机号 {acc['telephone']} 获取验证码"):
        code_resp = portal_sso_api.get_auth_code(acc["telephone"])
        A.assert_success(code_resp)
        auth_code = code_resp.data

    with allure.step("提交注册"):
        resp = portal_sso_api.register(acc["username"], acc["password"], acc["telephone"], auth_code)
        A.assert_success(resp, "注册成功")

    with allure.step("数据库校验：账号已落库且密码为 BCrypt 密文"):
        row = db.query_one(
            "select id, username, password, phone from ums_member where phone=%s", (acc["telephone"],)
        )
        assert row, f"库中未找到手机号 {acc['telephone']} 的会员记录"
        assert row["username"] == acc["username"]
        pwd = row["password"]
        assert pwd != acc["password"], "密码疑似明文入库"
        assert pwd.startswith("$2a$") and len(pwd) == 60, f"密码不是 BCrypt 密文：{pwd[:20]}..."


@allure.story("注册")
@allure.title("已注册手机号重复注册被拒绝")
@pytest.mark.case_id("MALL-POR-SSO-002")
def test_register_duplicate_phone(portal_sso_api, portal_member, db):
    with allure.step("用已注册手机号再次注册"):
        code_resp = portal_sso_api.get_auth_code(portal_member["telephone"])
        resp = portal_sso_api.register(
            data_factory.unique_username(), "Test@1234", portal_member["telephone"], code_resp.data
        )
    A.assert_failed(resp)

    with allure.step("库中该手机号仍只有一条记录"):
        cnt = db.count("ums_member", "phone=%s", (portal_member["telephone"],))
        assert cnt == 1, f"重复注册产生了多条会员记录：{cnt}"


@allure.story("注册")
@allure.title("验证码错误时注册失败")
@pytest.mark.case_id("MALL-POR-SSO-003")
def test_register_wrong_auth_code(portal_sso_api, db):
    acc = data_factory.member_account()
    resp = portal_sso_api.register(acc["username"], acc["password"], acc["telephone"], "000000")
    A.assert_failed(resp)

    cnt = db.count("ums_member", "phone=%s", (acc["telephone"],))
    assert cnt == 0, f"验证码错误却创建了会员：{cnt}"


@allure.story("登录")
@allure.title("注册用户登录成功并返回 token")
@pytest.mark.case_id("MALL-POR-SSO-004")
def test_login_success(portal_sso_api, portal_member):
    resp = portal_sso_api.login(portal_member["username"], portal_member["password"])
    A.assert_success(resp)
    data = A.assert_data_not_empty(resp)
    assert data.get("token"), f"token 为空：{resp}"
    assert data.get("tokenHead") == "Bearer "


@allure.story("登录")
@allure.title("登录失败时不泄露密码等敏感信息")
@pytest.mark.security
@pytest.mark.case_id("MALL-POR-SSO-006")
def test_login_failed_no_sensitive_leak(portal_sso_api, portal_member):
    resp = portal_sso_api.login(portal_member["username"], "Wrong@98765")
    A.assert_failed(resp)
    A.assert_no_sensitive_leak(resp)


@allure.story("验证码安全")
@allure.title("获取验证码接口不应明文返回验证码")
@pytest.mark.security
@pytest.mark.xfail(reason="已知缺陷 D-01：/sso/getAuthCode 直接返回 6 位明文验证码，可绕过手机号归属校验", strict=False)
@pytest.mark.case_id("MALL-POR-SSO-005")
def test_auth_code_not_returned_plaintext(portal_sso_api):
    resp = portal_sso_api.get_auth_code(data_factory.unique_phone("137"))
    A.assert_success(resp)
    data = str(resp.data or "")
    assert not (data.isdigit() and len(data) == 6), (
        f"接口直接返回了明文验证码 {data!r}，任意手机号均可注册，属高危安全问题"
    )
