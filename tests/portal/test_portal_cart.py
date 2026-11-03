"""前台购物车用例（对应 Excel：MALL-POR-CART-*）。"""
from __future__ import annotations

import allure
import pytest

from common import assertions as A

pytestmark = [
    pytest.mark.smoke,
    allure.epic("mall 商城"),
    allure.feature("前台-购物车"),
]


@allure.story("添加商品")
@allure.title("登录后添加商品，购物车列表出现该 SKU 且数量正确")
@pytest.mark.case_id("MALL-POR-CART-001")
def test_cart_add_and_list(portal_cart_api, clean_cart, sellable):
    with allure.step(f"加入购物车：productId={sellable['product_id']} skuId={sellable['sku_id']} quantity=1"):
        resp = portal_cart_api.add(sellable["product_id"], sellable["sku_id"], quantity=1)
        A.assert_success(resp)

    with allure.step("购物车列表应包含该 SKU 且 quantity=1"):
        listing = portal_cart_api.list()
        A.assert_success(listing)
        items = listing.data or []
        matched = [i for i in items if i.get("productSkuId") == sellable["sku_id"]]
        assert matched, f"购物车中未找到 SKU {sellable['sku_id']}，实际={[(i.get('productSkuId'), i.get('quantity')) for i in items]}"
        item = matched[0]
        assert item["quantity"] == 1, f"数量异常：{item['quantity']}"
        assert item.get("deleteStatus") == 0, f"加购后记录被标记删除：{item}"
        assert item.get("id"), "购物车项缺少主键 id"

    with allure.step("促销信息接口应带出促销与实时库存（/cart/list 只返回原始行）"):
        promo = portal_cart_api.list_promotion([item["id"]])
        A.assert_success(promo)
        promos = promo.data or []
        assert promos, "促销信息为空"
        p = promos[0]
        assert p.get("productSkuId") == sellable["sku_id"]
        assert int(p["realStock"]) >= int(p["quantity"]), f"实时库存不足：{p}"
        assert p.get("promotionMessage") is not None, "缺少促销提示字段"

    with allure.step("取购物车商品价格与名称（/cart/getProduct/{productId}）"):
        cp = portal_cart_api.get_product(sellable["product_id"])
        A.assert_success(cp)
        assert float(cp.data["price"]) > 0, f"价格异常：{cp.data.get('price')}"
        assert cp.data.get("name"), "商品名称为空"


@allure.story("添加商品")
@allure.title("同一 SKU 重复加购时数量累加")
@pytest.mark.case_id("MALL-POR-CART-003")
def test_cart_add_twice_accumulate(portal_cart_api, clean_cart, sellable):
    portal_cart_api.add(sellable["product_id"], sellable["sku_id"], quantity=1)
    portal_cart_api.add(sellable["product_id"], sellable["sku_id"], quantity=2)

    items = portal_cart_api.list().data or []
    matched = [i for i in items if i.get("productSkuId") == sellable["sku_id"]]
    assert matched, "加购后未出现在购物车"
    assert matched[0]["quantity"] == 3, f"重复加购未累加，实际 quantity={matched[0]['quantity']}"


@allure.story("权限")
@allure.title("未登录加购被拦截")
@pytest.mark.case_id("MALL-POR-CART-002")
def test_cart_add_without_token(portal_anon, sellable):
    resp = portal_anon.post("/cart/add", json_body={
        "productId": sellable["product_id"], "productSkuId": sellable["sku_id"], "quantity": 1,
    })
    A.assert_code(resp, 401)


@allure.story("清空购物车")
@allure.title("清空后购物车列表为空")
@pytest.mark.case_id("MALL-POR-CART-004")
def test_cart_clear(portal_cart_api, sellable):
    portal_cart_api.add(sellable["product_id"], sellable["sku_id"], quantity=1)
    A.assert_success(portal_cart_api.clear())
    items = portal_cart_api.list().data or []
    assert len(items) == 0, f"清空后仍有 {len(items)} 条数据"
