"""前台商品搜索（MALL-POR-SRC-*）。"""
from __future__ import annotations

import allure
import pytest

from common import assertions as A

pytestmark = [
    pytest.mark.regression,
    allure.epic("mall 商城"),
    allure.feature("前台-搜索"),
]


@allure.story("搜索")
@allure.title("关键字搜索返回匹配商品")
@pytest.mark.case_id("MALL-POR-SRC-001")
def test_search_keyword(portal_product_api):
    resp = portal_product_api.search("手机", page_num=1, page_size=5)
    A.assert_success(resp)
    data = A.assert_data_not_empty(resp)
    assert data["total"] >= 1
    assert len(data["list"]) <= 5


@allure.story("搜索")
@allure.title("分页参数生效：pageSize=1 只返回 1 条")
@pytest.mark.case_id("MALL-POR-SRC-002")
def test_search_page_size(portal_product_api):
    resp = portal_product_api.search("手机", page_num=1, page_size=1)
    A.assert_success(resp)
    assert len(resp.data["list"]) == 1, f"pageSize 未生效，实际 {len(resp.data['list'])} 条"


@allure.story("搜索")
@allure.title("不存在的关键字返回空列表而非报错")
@pytest.mark.case_id("MALL-POR-SRC-003")
def test_search_no_result(portal_product_api):
    resp = portal_product_api.search("zzz_不存在的商品_9527")
    A.assert_success(resp)
    assert resp.data["list"] == [], f"无结果时应返回空列表：{resp.data['list']}"


@allure.story("搜索")
@allure.title("特殊字符关键字不导致服务端异常")
@pytest.mark.case_id("MALL-POR-SRC-004")
def test_search_special_chars(portal_product_api):
    resp = portal_product_api.search("%_\\'\"<>")
    A.assert_success(resp)
    assert isinstance(resp.data.get("list"), list)


@allure.story("搜索")
@allure.title("超长关键字不导致服务端异常")
@pytest.mark.case_id("MALL-POR-SRC-005")
def test_search_long_keyword(portal_product_api):
    resp = portal_product_api.search("手" * 500)
    A.assert_success(resp)
    assert isinstance(resp.data.get("list"), list)


@allure.story("搜索安全")
@allure.title("SQL 注入关键字不生效且不泄露 SQL 错误")
@pytest.mark.security
@pytest.mark.case_id("MALL-POR-SRC-006")
def test_search_sql_injection(portal_product_api):
    payload = "' OR 1=1 -- "
    resp = portal_product_api.search(payload)
    A.assert_success(resp)
    assert "SQL" not in str(resp.body), f"响应泄露 SQL 错误：{resp.body}"
    total_injected = resp.data.get("total")
    normal = portal_product_api.search("商品").data.get("total")
    assert total_injected != normal or total_injected == 0, "注入关键字疑似绕过了条件"
