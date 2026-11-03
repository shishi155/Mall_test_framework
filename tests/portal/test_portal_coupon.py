"""前台优惠券与营销（MALL-POR-CPN-*）。"""
from __future__ import annotations

import allure
import pytest

from common import assertions as A

pytestmark = [
    pytest.mark.regression,
    allure.epic("mall 商城"),
    allure.feature("前台-优惠券"),
]


@pytest.fixture()
def coupon_ids(admin_marketing_api):
    resp = admin_marketing_api.coupon_list(page_size=20)
    assert resp.code == 200, f"后台优惠券列表失败：{resp}"
    ids = [c["id"] for c in (resp.data.get("list") or [])]
    assert ids, "环境中没有优惠券数据，无法测试领取"
    return ids


@pytest.fixture()
def single_limit_coupon(admin_marketing_api):
    """取一张「每人限领 1 张」的券，用于重复领取校验。"""
    resp = admin_marketing_api.coupon_list(page_size=50)
    assert resp.code == 200, f"后台优惠券列表失败：{resp}"
    for c in (resp.data.get("list") or []):
        if int(c.get("perLimit") or 0) == 1:
            return c["id"]
    pytest.skip("环境没有 perLimit=1 的优惠券，无法验证限领规则")


@allure.story("领取优惠券")
@allure.title("领取优惠券后可在我的优惠券中查到")
@pytest.mark.case_id("MALL-POR-CPN-001")
def test_coupon_receive(member_coupon_api, coupon_ids):
    coupon_id = coupon_ids[0]
    resp = member_coupon_api.add(coupon_id)

    if resp.code != 200:
        # 已领取/已抢光属于业务限制，不算失败，但要能给出明确提示
        assert resp.message, "领取失败却无提示"
        pytest.skip(f"该券不可领取：{resp.message}")

    mine = member_coupon_api.list()
    A.assert_success(mine)
    assert any(c["id"] == coupon_id for c in (mine.data or [])), f"领取后未出现在我的优惠券：{mine.data}"


@allure.story("领取优惠券")
@allure.title("同一优惠券重复领取应被限制（perLimit=1）")
@pytest.mark.case_id("MALL-POR-CPN-002")
def test_coupon_receive_twice(member_coupon_api, single_limit_coupon):
    coupon_id = single_limit_coupon
    first = member_coupon_api.add(coupon_id)
    if first.code != 200:
        pytest.skip(f"该券首次即不可领：{first.message}")

    member_coupon_api.add(coupon_id)
    history = [h for h in (member_coupon_api.list_history().data or []) if h.get("couponId") == coupon_id]
    assert len(history) <= 1, f"perLimit=1 的券被领取了 {len(history)} 次"


@allure.story("我的优惠券")
@allure.title("按使用状态筛选优惠券")
@pytest.mark.case_id("MALL-POR-CPN-003")
def test_coupon_list_by_status(member_coupon_api):
    unused = member_coupon_api.list(use_status=0)
    A.assert_success(unused)
    assert isinstance(unused.data, list)
    used = member_coupon_api.list(use_status=1)
    A.assert_success(used)
    assert isinstance(used.data, list)


@allure.story("我的优惠券")
@allure.title("优惠券领取历史可查询")
@pytest.mark.case_id("MALL-POR-CPN-004")
def test_coupon_history(member_coupon_api):
    resp = member_coupon_api.list_history()
    A.assert_success(resp)
    assert isinstance(resp.data, list)


@allure.story("优惠券")
@allure.title("下单可用券列表可按商品查询")
@pytest.mark.case_id("MALL-POR-CPN-005")
def test_coupon_list_by_product(member_coupon_api, sellable):
    resp = member_coupon_api.list_by_product(sellable["product_id"])
    A.assert_success(resp)
    assert isinstance(resp.data, list)


@allure.story("优惠券")
@allure.title("购物车可用券列表接口可用")
@pytest.mark.case_id("MALL-POR-CPN-006")
def test_coupon_list_cart(member_coupon_api):
    resp = member_coupon_api.list_cart(0)
    A.assert_success(resp)
    assert isinstance(resp.data, list)


@allure.story("权限")
@allure.title("未登录访问我的优惠券被拦截")
@pytest.mark.case_id("MALL-POR-CPN-007")
def test_coupon_without_token(portal_anon):
    A.assert_code(portal_anon.get("/member/coupon/list"), 401)
