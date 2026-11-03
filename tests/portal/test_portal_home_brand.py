"""前台首页 / 分类 / 品牌（MALL-POR-HOME-*）。"""
from __future__ import annotations

import allure
import pytest

from common import assertions as A

pytestmark = [
    pytest.mark.smoke,
    allure.epic("mall 商城"),
    allure.feature("前台-首页与品牌"),
]


@allure.story("首页")
@allure.title("首页热门/新品/推荐商品列表非空")
@pytest.mark.case_id("MALL-POR-HOME-002")
def test_home_product_lists(portal_home_api):
    for name, api in (("hot", portal_home_api.hot_product_list),
                      ("new", portal_home_api.new_product_list),
                      ("recommend", portal_home_api.recommend_product_list)):
        resp = api()
        A.assert_success(resp)
        data = A.assert_data_not_empty(resp)
        assert isinstance(data, list) or isinstance(data, dict), f"{name} 返回结构异常：{type(data)}"


@allure.story("首页")
@allure.title("首页分类列表按父级返回")
@pytest.mark.case_id("MALL-POR-HOME-003")
def test_home_category_list(portal_client):
    resp = portal_client.get("/home/productCateList/0")
    A.assert_success(resp)
    assert isinstance(resp.data, list), f"分类返回结构异常：{resp.data}"


@allure.story("首页")
@allure.title("首页专题列表可查询")
@pytest.mark.case_id("MALL-POR-HOME-004")
def test_home_subject_list(portal_client):
    resp = portal_client.get("/home/subjectList")
    A.assert_success(resp)
    assert isinstance(resp.data, list)


@allure.story("分类")
@allure.title("商品分类树返回两级以上结构")
@pytest.mark.case_id("MALL-POR-HOME-005")
def test_category_tree(portal_product_api):
    resp = portal_product_api.category_tree()
    A.assert_success(resp)
    tree = A.assert_data_not_empty(resp)
    assert isinstance(tree, list) and tree, "分类树为空"
    first = tree[0]
    assert "children" in first, f"分类节点缺少 children：{list(first.keys())}"


@allure.story("品牌")
@allure.title("推荐品牌列表非空")
@pytest.mark.case_id("MALL-POR-BRAND-001")
def test_brand_recommend(portal_client):
    resp = portal_client.get("/brand/recommendList")
    A.assert_success(resp)
    brands = A.assert_data_not_empty(resp)
    assert all(b.get("id") for b in brands)


@allure.story("品牌")
@allure.title("品牌详情与品牌商品列表一致")
@pytest.mark.case_id("MALL-POR-BRAND-002")
def test_brand_detail_and_products(portal_client):
    brands = portal_client.get("/brand/recommendList").data or []
    assert brands, "无推荐品牌"
    brand_id = brands[0]["id"]

    detail = portal_client.get(f"/brand/detail/{brand_id}")
    A.assert_success(detail)
    assert detail.data["id"] == brand_id

    products = portal_client.get("/brand/productList", params={"brandId": brand_id, "pageNum": 1, "pageSize": 5})
    A.assert_success(products)
    assert isinstance(products.data, dict)
    for p in (products.data.get("list") or []):
        assert p.get("brandId") == brand_id, f"品牌商品列表混入其他品牌：{p.get('brandId')}"


@allure.story("品牌")
@allure.title("品牌不存在时返回可判定的错误")
@pytest.mark.xfail(reason="已知缺陷 D-02：不存在的资源返回 HTTP500 且业务码错乱（/error 未放行导致异常被安全框架吞掉）", strict=False)
@pytest.mark.case_id("MALL-POR-BRAND-003")
def test_brand_not_exist(portal_client):
    resp = portal_client.get("/brand/detail/999999")
    assert resp.status_code == 200, f"HTTP 状态码异常：{resp.status_code}"
    A.assert_failed(resp, expected_codes=(404, 500))
