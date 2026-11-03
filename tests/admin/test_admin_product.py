"""后台商品管理（MALL-ADM-PRD-*）。"""
from __future__ import annotations

import allure
import pytest

from common import assertions as A

pytestmark = [
    pytest.mark.regression,
    allure.epic("mall 商城"),
    allure.feature("后台-商品管理"),
]


@pytest.fixture(scope="module")
def target_product(db):
    """挑一个未删除的商品用于状态类操作，用例结束后恢复。"""
    row = db.query_one(
        "select id, publish_status, verify_status, recommand_status, new_status, delete_status "
        "from pms_product where delete_status = 0 order by id limit 1"
    )
    assert row, "库中没有可用商品"
    return row


@allure.story("商品列表")
@allure.title("按关键字搜索商品")
@pytest.mark.case_id("MALL-ADM-PRD-002")
def test_product_list_by_keyword(admin_product_api):
    resp = admin_product_api.list(keyword="手机")
    A.assert_success(resp)
    data = A.assert_data_not_empty(resp)
    for item in data["list"]:
        assert "手机" in (item.get("name") or ""), f"搜索结果包含不匹配商品：{item.get('name')}"


@allure.story("商品列表")
@allure.title("分页 pageSize 生效")
@pytest.mark.case_id("MALL-ADM-PRD-003")
def test_product_list_page_size(admin_product_api):
    resp = admin_product_api.list(page_num=1, page_size=2)
    A.assert_success(resp)
    assert len(resp.data["list"]) <= 2, f"pageSize 未生效：{len(resp.data['list'])}"


@allure.story("商品列表")
@allure.title("关键字无匹配时返回空列表")
@pytest.mark.case_id("MALL-ADM-PRD-004")
def test_product_list_no_match(admin_product_api):
    resp = admin_product_api.list(keyword="zzz_不存在_9527")
    A.assert_success(resp)
    assert resp.data["list"] == []


@allure.story("商品下拉")
@allure.title("simpleList 返回商品精简列表")
@pytest.mark.case_id("MALL-ADM-PRD-005")
def test_product_simple_list(admin_product_api):
    resp = admin_product_api.simple_list()
    A.assert_success(resp)
    items = A.assert_data_not_empty(resp)
    assert all(i.get("id") for i in items)


@allure.story("商品详情")
@allure.title("编辑页详情返回商品与 SKU 信息")
@pytest.mark.case_id("MALL-ADM-PRD-006")
def test_product_update_info(admin_product_api, target_product):
    resp = admin_product_api.update_info(target_product["id"])
    A.assert_success(resp)
    data = A.assert_data_not_empty(resp)
    assert data.get("id") == target_product["id"]
    assert "skuStockList" in data, f"编辑详情缺少 SKU 列表：{list(data.keys())}"


@allure.story("商品状态")
@allure.title("上架/下架状态切换并落库")
@pytest.mark.case_id("MALL-ADM-PRD-007")
def test_product_publish_status(admin_product_api, target_product, db):
    pid = target_product["id"]
    original = int(target_product["publish_status"])
    try:
        A.assert_success(admin_product_api.update_publish_status([pid], 0))
        assert int(db.query_one("select publish_status from pms_product where id=%s", (pid,))["publish_status"]) == 0
        A.assert_success(admin_product_api.update_publish_status([pid], 1))
        assert int(db.query_one("select publish_status from pms_product where id=%s", (pid,))["publish_status"]) == 1
    finally:
        admin_product_api.update_publish_status([pid], original)


@allure.story("商品状态")
@allure.title("审核状态更新")
@pytest.mark.case_id("MALL-ADM-PRD-008")
def test_product_verify_status(admin_product_api, target_product, db):
    pid = target_product["id"]
    original = int(target_product["verify_status"])
    try:
        A.assert_success(admin_product_api.update_verify_status([pid], 1, "审核通过"))
        assert int(db.query_one("select verify_status from pms_product where id=%s", (pid,))["verify_status"]) == 1
    finally:
        admin_product_api.update_verify_status([pid], original, "")


@allure.story("商品状态")
@allure.title("推荐/新品状态更新")
@pytest.mark.case_id("MALL-ADM-PRD-009")
def test_product_recommend_and_new_status(admin_product_api, target_product, db):
    pid = target_product["id"]
    r0 = int(target_product["recommand_status"])
    n0 = int(target_product["new_status"])
    try:
        A.assert_success(admin_product_api.update_recommend_status([pid], 1))
        A.assert_success(admin_product_api.update_new_status([pid], 1))
        row = db.query_one("select recommand_status, new_status from pms_product where id=%s", (pid,))
        assert int(row["recommand_status"]) == 1 and int(row["new_status"]) == 1
    finally:
        admin_product_api.update_recommend_status([pid], r0)
        admin_product_api.update_new_status([pid], n0)


@allure.story("商品状态")
@allure.title("软删除商品后列表中不再出现，可恢复")
@pytest.mark.case_id("MALL-ADM-PRD-010")
def test_product_delete_and_restore(admin_product_api, target_product, db):
    pid = target_product["id"]
    try:
        A.assert_success(admin_product_api.update_delete_status([pid], 1))
        assert int(db.query_one("select delete_status from pms_product where id=%s", (pid,))["delete_status"]) == 1

        listing = admin_product_api.list(page_size=50)
        assert all(i["id"] != pid for i in listing.data["list"]), "已删除商品仍出现在列表"
    finally:
        admin_product_api.update_delete_status([pid], 0)


@allure.story("商品编辑")
@allure.title("更新不存在的商品返回可判定错误")
@pytest.mark.case_id("MALL-ADM-PRD-011")
def test_product_update_not_exist(admin_product_api):
    resp = admin_product_api.update(999999, {"name": "x"})
    assert resp.code != 200 or resp.message, f"更新不存在商品返回异常：{resp}"


@allure.story("权限")
@allure.title("未登录访问商品管理接口被拦截")
@pytest.mark.case_id("MALL-ADM-PRD-012")
def test_product_list_without_token(admin_anon):
    A.assert_code(admin_anon.get("/product/list", params={"pageNum": 1, "pageSize": 5}), 401)
