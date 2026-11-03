"""后台订单管理（MALL-ADM-ORD-*）。"""
from __future__ import annotations

import allure
import pytest

from common import assertions as A
from common.order_flow import create_order

pytestmark = [
    pytest.mark.regression,
    allure.epic("mall 商城"),
    allure.feature("后台-订单管理"),
]


@pytest.fixture()
def paid_order(shopper, orderable):
    """造一笔「已支付待发货」订单，供发货类用例使用。"""
    _, created, _ = create_order(shopper, orderable)
    order = created["order"]
    resp = shopper.client.post("/order/paySuccess", params={"orderId": order["id"], "payType": 0})
    assert resp.code == 200, f"模拟支付失败：{resp}"
    return {"id": order["id"], "orderSn": order["orderSn"], "memberId": order["memberId"]}


@pytest.fixture()
def pending_order(shopper, orderable):
    """造一笔「待付款」订单，供关闭类用例使用。"""
    _, created, _ = create_order(shopper, orderable)
    return created["order"]


@allure.story("订单列表")
@allure.title("按状态筛选订单")
@pytest.mark.case_id("MALL-ADM-ORD-001")
def test_order_list_by_status(admin_order_api, paid_order):
    resp = admin_order_api.list(status=1, page_size=10)
    A.assert_success(resp)
    data = A.assert_data_not_empty(resp)
    assert all(int(i["status"]) == 1 for i in data["list"]), "列表含非待发货订单"


@allure.story("订单列表")
@allure.title("按订单号精确查询")
@pytest.mark.case_id("MALL-ADM-ORD-002")
def test_order_list_by_sn(admin_order_api, paid_order):
    resp = admin_order_api.list(order_sn=paid_order["orderSn"], page_size=10)
    A.assert_success(resp)
    sns = [i["orderSn"] for i in resp.data["list"]]
    assert paid_order["orderSn"] in sns, f"订单号查询未命中：{sns}"


@allure.story("订单详情")
@allure.title("订单详情包含明细与收货信息")
@pytest.mark.case_id("MALL-ADM-ORD-003")
def test_order_detail(admin_order_api, paid_order):
    resp = admin_order_api.detail(paid_order["id"])
    A.assert_success(resp)
    data = A.assert_data_not_empty(resp)
    for key in ("id", "orderSn", "status", "orderItemList", "receiverName", "receiverPhone"):
        assert key in data, f"订单详情缺少 {key}"


@allure.story("订单发货")
@allure.title("发货后订单状态变为已发货并记录物流单号")
@pytest.mark.smoke
@pytest.mark.case_id("MALL-ADM-ORD-004")
def test_order_delivery(admin_order_api, paid_order, db):
    resp = admin_order_api.delivery([{
        "orderId": paid_order["id"], "deliveryCompany": "顺丰速运", "deliverySn": "SF1234567890",
    }])
    A.assert_success(resp)

    row = db.query_one("select status, delivery_company, delivery_sn from oms_order where id=%s", (paid_order["id"],))
    assert int(row["status"]) == 2, f"发货后状态应为 2，实际 {row['status']}"
    assert row["delivery_company"] == "顺丰速运"
    assert row["delivery_sn"] == "SF1234567890"


@allure.story("订单发货")
@allure.title("未支付订单不能发货")
@pytest.mark.case_id("MALL-ADM-ORD-005")
def test_order_delivery_unpaid(admin_order_api, pending_order, db):
    resp = admin_order_api.delivery([{
        "orderId": pending_order["id"], "deliveryCompany": "顺丰", "deliverySn": "SF0001",
    }])
    row = db.query_one("select status from oms_order where id=%s", (pending_order["id"],))
    assert resp.code != 200 or int(row["status"]) == 0, f"未支付订单被发货：{resp}"


@allure.story("关闭订单")
@allure.title("关闭待付款订单后状态变为已关闭")
@pytest.mark.case_id("MALL-ADM-ORD-006")
def test_order_close(admin_order_api, pending_order, db):
    resp = admin_order_api.close([pending_order["id"]], "测试关闭")
    A.assert_success(resp)
    row = db.query_one("select status from oms_order where id=%s", (pending_order["id"],))
    assert int(row["status"]) == 4, f"关闭后状态应为 4，实际 {row['status']}"

    # 关闭备注记录在操作历史表（oms_order_operate_history），不是主表 note 字段
    history = db.query_one(
        "select order_status, note from oms_order_operate_history where order_id=%s order by id desc limit 1",
        (pending_order["id"],),
    )
    assert history, "关闭订单未写入操作历史"
    assert int(history["order_status"]) == 4
    assert "测试关闭" in (history["note"] or ""), f"关闭备注未记录：{history['note']}"


@allure.story("订单修改")
@allure.title("修改订单备注")
@pytest.mark.case_id("MALL-ADM-ORD-007")
def test_order_update_note(admin_order_api, paid_order, db):
    resp = admin_order_api.update_note(paid_order["id"], "后台补充备注", 0)
    A.assert_success(resp)
    row = db.query_one("select note from oms_order where id=%s", (paid_order["id"],))
    assert "后台补充备注" in (row["note"] or "")


@allure.story("订单修改")
@allure.title("修改收货人信息")
@pytest.mark.case_id("MALL-ADM-ORD-008")
def test_order_update_receiver(admin_order_api, paid_order, db):
    resp = admin_order_api.update_receiver_info({
        "orderId": paid_order["id"], "receiverName": "后台改", "receiverPhone": "13900001111",
        "receiverPostCode": "518000", "receiverProvince": "广东省", "receiverCity": "深圳市",
        "receiverRegion": "南山区", "receiverDetailAddress": "后台改地址",
    })
    A.assert_success(resp)
    row = db.query_one("select receiver_name, receiver_phone from oms_order where id=%s", (paid_order["id"],))
    assert row["receiver_name"] == "后台改"


@allure.story("权限")
@allure.title("未登录访问订单管理接口被拦截")
@pytest.mark.case_id("MALL-ADM-ORD-009")
def test_order_list_without_token(admin_anon):
    A.assert_code(admin_anon.get("/order/list", params={"pageNum": 1, "pageSize": 5}), 401)
