"""后台营销与基础数据（MALL-ADM-MKT-* / MALL-ADM-BASE-*）。"""
from __future__ import annotations

import time

import allure
import pytest

from common import assertions as A
from common import data_factory

pytestmark = [
    pytest.mark.regression,
    allure.epic("mall 商城"),
    allure.feature("后台-营销与基础数据"),
]


# ---------------- 营销：优惠券 ----------------
@allure.story("优惠券")
@allure.title("优惠券列表可查询、可分页")
@pytest.mark.case_id("MALL-ADM-MKT-001")
def test_coupon_list(admin_marketing_api):
    resp = admin_marketing_api.coupon_list(page_size=5)
    A.assert_success(resp)
    data = A.assert_data_not_empty(resp)
    assert len(data["list"]) <= 5


@allure.story("优惠券")
@allure.title("优惠券详情返回参数信息")
@pytest.mark.case_id("MALL-ADM-MKT-002")
def test_coupon_detail(admin_marketing_api):
    listing = admin_marketing_api.coupon_list(page_size=1)
    coupon_id = listing.data["list"][0]["id"]
    resp = admin_marketing_api.coupon_detail(coupon_id)
    A.assert_success(resp)
    data = A.assert_data_not_empty(resp)
    assert data.get("id") == coupon_id


@allure.story("优惠券")
@allure.title("创建优惠券后可查询并删除")
@pytest.mark.case_id("MALL-ADM-MKT-003")
def test_coupon_create_and_delete(admin_marketing_api, db):
    now = int(time.time() * 1000)
    name = f"自动化券_{data_factory.unique_username(prefix='')}"
    payload = {
        "name": name, "type": 0, "platform": 0, "count": 100, "amount": 10, "perLimit": 1,
        "minPoint": 100, "startTime": now, "endTime": now + 7 * 86400 * 1000,
        "note": "自动化创建", "useType": 0,
    }
    resp = admin_marketing_api.coupon_create(payload)
    A.assert_success(resp)

    row = db.query_one("select id, name from sms_coupon where name=%s order by id desc limit 1", (name,))
    assert row, "优惠券未落库"

    A.assert_success(admin_marketing_api.coupon_delete(int(row["id"])))
    assert db.query_one("select id from sms_coupon where id=%s", (row["id"],)) is None, "优惠券未删除"


@allure.story("秒杀")
@allure.title("秒杀场次与活动列表可查询")
@pytest.mark.case_id("MALL-ADM-MKT-004")
def test_flash_promotion(admin_marketing_api):
    sessions = admin_marketing_api.flash_session_list()
    A.assert_success(sessions)
    assert isinstance(sessions.data, (list, dict)), f"秒杀场次返回结构异常：{type(sessions.data)}"

    flashes = admin_marketing_api.flash_list()
    A.assert_success(flashes)
    assert isinstance(flashes.data, (list, dict)), f"秒杀活动返回结构异常：{type(flashes.data)}"


@allure.story("首页运营")
@allure.title("首页广告列表可查询")
@pytest.mark.case_id("MALL-ADM-MKT-005")
def test_home_advertise(admin_marketing_api):
    resp = admin_marketing_api.advertise_list(page_size=5)
    A.assert_success(resp)
    assert isinstance(resp.data.get("list"), list)


# ---------------- 基础数据 ----------------
@allure.story("基础数据")
@allure.title("会员等级列表")
@pytest.mark.case_id("MALL-ADM-BASE-001")
def test_member_level(admin_base_api):
    resp = admin_base_api.member_level_list()
    A.assert_success(resp)
    assert isinstance(resp.data, list)


@allure.story("基础数据")
@allure.title("公司发货地址列表")
@pytest.mark.case_id("MALL-ADM-BASE-002")
def test_company_address(admin_base_api):
    resp = admin_base_api.company_address_list()
    A.assert_success(resp)
    assert isinstance(resp.data, list)


@allure.story("基础数据")
@allure.title("专题与偏好专区列表")
@pytest.mark.case_id("MALL-ADM-BASE-003")
def test_subject_and_prefrence(admin_base_api):
    subjects = admin_base_api.subject_list()
    A.assert_success(subjects)
    assert isinstance(subjects.data, list)

    areas = admin_base_api.prefrence_area_list()
    A.assert_success(areas)
    assert isinstance(areas.data, list)


@allure.story("基础数据")
@allure.title("订单设置读取")
@pytest.mark.case_id("MALL-ADM-BASE-004")
def test_order_setting(admin_base_api):
    resp = admin_base_api.order_setting(1)
    A.assert_success(resp)
    data = A.assert_data_not_empty(resp)
    assert data.get("id") == 1


@allure.story("基础数据")
@allure.title("退货原因列表")
@pytest.mark.case_id("MALL-ADM-BASE-005")
def test_return_reason(admin_base_api):
    resp = admin_base_api.return_reason_list()
    A.assert_success(resp)
    assert isinstance(resp.data.get("list"), list)


@allure.story("权限")
@allure.title("未登录访问基础数据接口被拦截")
@pytest.mark.case_id("MALL-ADM-BASE-006")
def test_base_without_token(admin_anon):
    A.assert_code(admin_anon.get("/memberLevel/list", params={"defaultStatus": 0}), 401)
