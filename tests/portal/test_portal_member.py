"""前台会员中心：收藏 / 浏览记录 / 品牌关注（MALL-POR-MEM-*）。"""
from __future__ import annotations

import allure
import pytest

from common import assertions as A
from common import data_factory

pytestmark = [
    pytest.mark.regression,
    allure.epic("mall 商城"),
    allure.feature("前台-会员中心"),
]


def product_payload(product_id: int, detail: dict) -> dict:
    """构造收藏/足迹所需的商品快照字段。"""
    p = detail["product"]
    return {
        "productId": product_id,
        "productName": p.get("name"),
        "productPic": p.get("pic"),
        "productPrice": p.get("price"),
        "productSubTitle": p.get("subTitle"),
        "createTime": "2026-01-01T00:00:00.000+00:00",
    }


@pytest.fixture()
def product_info(portal_client, sellable):
    detail = data_factory.get_product_detail(portal_client, sellable["product_id"])
    return product_payload(sellable["product_id"], detail), sellable["product_id"]


# ---------------- 收藏 ----------------
@allure.story("商品收藏")
@allure.title("添加收藏后可在列表与详情中查到")
@pytest.mark.case_id("MALL-POR-MEM-001")
def test_collection_add(member_collection_api, product_info):
    payload, pid = product_info
    member_collection_api.clear()
    A.assert_success(member_collection_api.add(payload))

    listing = member_collection_api.list()
    A.assert_success(listing)
    ids = [i["productId"] for i in (listing.data.get("list") or [])]
    assert pid in ids, f"收藏列表未包含商品 {pid}，实际 {ids}"

    detail = member_collection_api.detail(pid)
    A.assert_success(detail)
    assert detail.data["productId"] == pid


@allure.story("商品收藏")
@allure.title("重复收藏同一商品不应产生重复记录")
@pytest.mark.case_id("MALL-POR-MEM-002")
def test_collection_add_twice(member_collection_api, product_info):
    payload, pid = product_info
    member_collection_api.clear()
    member_collection_api.add(payload)
    member_collection_api.add(payload)

    listing = member_collection_api.list().data.get("list") or []
    same = [i for i in listing if i["productId"] == pid]
    assert len(same) == 1, f"同一商品出现 {len(same)} 条收藏记录"


@allure.story("商品收藏")
@allure.title("取消收藏后列表不再包含该商品")
@pytest.mark.case_id("MALL-POR-MEM-003")
def test_collection_delete(member_collection_api, product_info):
    payload, pid = product_info
    member_collection_api.clear()
    member_collection_api.add(payload)

    A.assert_success(member_collection_api.delete(pid))
    listing = member_collection_api.list().data.get("list") or []
    assert all(i["productId"] != pid for i in listing), "取消收藏后仍存在"


@allure.story("商品收藏")
@allure.title("清空收藏后列表为空")
@pytest.mark.case_id("MALL-POR-MEM-004")
def test_collection_clear(member_collection_api, product_info):
    payload, _ = product_info
    member_collection_api.add(payload)
    A.assert_success(member_collection_api.clear())
    listing = member_collection_api.list().data.get("list") or []
    assert listing == [], f"清空后仍有 {len(listing)} 条"


@allure.story("商品收藏")
@allure.title("未登录访问收藏接口被拦截")
@pytest.mark.case_id("MALL-POR-MEM-005")
def test_collection_without_token(portal_anon):
    A.assert_code(portal_anon.get("/member/productCollection/list"), 401)


# ---------------- 浏览记录 ----------------
@allure.story("浏览记录")
@allure.title("新增浏览记录后可在列表中分页查询")
@pytest.mark.case_id("MALL-POR-MEM-006")
def test_history_create_and_list(member_history_api, product_info):
    payload, pid = product_info
    member_history_api.clear()
    A.assert_success(member_history_api.create(payload))

    listing = member_history_api.list(page_num=1, page_size=10)
    A.assert_success(listing)
    data = A.assert_data_not_empty(listing)
    assert data["total"] >= 1
    assert any(i["productId"] == pid for i in data["list"]), f"浏览记录未包含商品 {pid}"


@allure.story("浏览记录")
@allure.title("清空浏览记录后列表为空")
@pytest.mark.case_id("MALL-POR-MEM-007")
def test_history_clear(member_history_api, product_info):
    payload, _ = product_info
    member_history_api.create(payload)
    A.assert_success(member_history_api.clear())
    data = member_history_api.list().data
    assert (data or {}).get("list") == [], f"清空后仍有记录：{data}"


# ---------------- 品牌关注 ----------------
@allure.story("品牌关注")
@allure.title("关注品牌后可在关注列表查到并取消")
@pytest.mark.case_id("MALL-POR-MEM-008")
def test_attention_add_and_delete(member_attention_api, portal_home_api):
    brands = portal_home_api.content().data.get("brandList") or []
    assert brands, "首页无品牌数据，无法构造关注场景"
    brand = brands[0]

    member_attention_api.clear()
    A.assert_success(member_attention_api.add({
        "brandId": brand["id"], "brandName": brand.get("name"), "brandLogo": brand.get("logo"),
    }))

    listing = member_attention_api.list()
    A.assert_success(listing)
    # /member/attention/list 返回 CommonPage（data.list），不是裸数组
    ids = [i["brandId"] for i in (listing.data.get("list") or [])]
    assert brand["id"] in ids, f"关注列表未包含品牌 {brand['id']}，实际 {ids}"

    A.assert_success(member_attention_api.delete(brand["id"]))
    ids_after = [i["brandId"] for i in (member_attention_api.list().data.get("list") or [])]
    assert brand["id"] not in ids_after, "取消关注后仍存在"


@allure.story("品牌关注")
@allure.title("未登录访问关注接口被拦截")
@pytest.mark.case_id("MALL-POR-MEM-009")
def test_attention_without_token(portal_anon):
    A.assert_code(portal_anon.get("/member/attention/list"), 401)
