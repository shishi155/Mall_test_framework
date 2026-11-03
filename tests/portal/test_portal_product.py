"""前台商品浏览与搜索用例（对应 Excel：MALL-POR-PRD-*）。"""
from __future__ import annotations

import allure
import pytest

from common import assertions as A
from common import data_factory

pytestmark = [
    pytest.mark.smoke,
    allure.epic("mall 商城"),
    allure.feature("前台-商品浏览"),
]


@allure.story("商品详情")
@allure.title("查询在售商品详情，SKU 库存与数据库一致")
@pytest.mark.case_id("MALL-POR-PRD-001")
def test_product_detail(portal_product_api, sellable, db):
    """商品与 SKU 来自数据库（已上架 + 有库存），避免写死 id 导致假失败。"""
    pid, sku_id = sellable["product_id"], sellable["sku_id"]

    resp = portal_product_api.detail(pid)
    A.assert_success(resp)
    data = A.assert_data_not_empty(resp)

    with allure.step("校验商品主信息"):
        product = data["product"]
        A.assert_fields(product, {"id": pid})
        assert product.get("name"), "商品名称为空"
        assert product.get("price") is not None, "商品价格为空"

    with allure.step(f"详情中应包含 SKU {sku_id}，且库存与库中一致"):
        skus = data.get("skuStockList") or []
        matched = [s for s in skus if int(s["id"]) == sku_id]
        assert matched, f"详情未返回 SKU {sku_id}，实际返回 {[s.get('id') for s in skus]}"
        row = db.query_one("select stock, price from pms_sku_stock where id=%s", (sku_id,))
        assert int(matched[0]["stock"]) == int(row["stock"]), (
            f"SKU 库存不一致：接口 {matched[0]['stock']}，库中 {row['stock']}"
        )


@allure.story("商品详情")
@allure.title("查询不存在的商品应返回可判定的业务错误")
@pytest.mark.xfail(reason="已知缺陷 D-02：/product/detail/{不存在id} 返回 HTTP500，且业务码为 401", strict=False)
@pytest.mark.case_id("MALL-POR-PRD-002")
def test_product_detail_not_exist(portal_product_api):
    resp = portal_product_api.detail(999999)
    assert resp.status_code == 200, f"期望 HTTP 200，实际 {resp.status_code}"
    A.assert_failed(resp, expected_codes=(404, 500))


@allure.story("商品搜索")
@allure.title("关键字搜索返回分页商品列表")
@pytest.mark.case_id("MALL-POR-PRD-003")
def test_product_search(portal_product_api):
    resp = portal_product_api.search("手机", page_num=1, page_size=5)
    A.assert_success(resp)
    data = A.assert_data_not_empty(resp)
    assert data["total"] > 0, "搜索「手机」无结果，商品库可能未初始化"
    assert len(data["list"]) <= 5
    for item in data["list"]:
        assert item.get("id") and item.get("name")


@allure.story("商品搜索")
@allure.title("空关键字搜索不报错（边界）")
@pytest.mark.regression
@pytest.mark.case_id("MALL-POR-PRD-004")
def test_product_search_blank_keyword(portal_product_api):
    resp = portal_product_api.search("", page_num=1, page_size=5)
    A.assert_success(resp)
    assert isinstance(resp.data, dict), f"返回结构异常：{resp.data}"
    assert isinstance(resp.data.get("list"), list)


@allure.story("首页")
@allure.title("首页聚合内容 6 类数据齐全")
@pytest.mark.case_id("MALL-POR-HOME-001")
def test_home_content(portal_home_api):
    resp = portal_home_api.content()
    A.assert_success(resp)
    data = A.assert_data_not_empty(resp)
    for key in ("advertiseList", "brandList", "newProductList", "hotProductList", "subjectList"):
        assert key in data, f"首页缺少 {key}，实际字段={list(data.keys())}"
