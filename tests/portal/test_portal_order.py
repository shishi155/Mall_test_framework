"""前台订单用例：确认单 → 下单 → 支付 → 取消 → 删除（MALL-POR-ORD-*）。

说明：mall-portal 的优惠计算对「无优惠/打折/满减」商品会抛 NPE（缺陷 D-06），
因此下单链路统一使用 `orderable` 夹具（promotion_type=1 且有促销价）。
"""
from __future__ import annotations

import allure
import pytest

from common import assertions as A
from common.order_flow import create_order, fill_cart

pytestmark = [
    allure.epic("mall 商城"),
    allure.feature("前台-订单"),
]


# ---------------- 确认单 ----------------
@allure.story("确认单")
@allure.title("确认单金额计算正确（原价/促销/应付）")
@pytest.mark.smoke
@pytest.mark.case_id("MALL-POR-ORD-001")
def test_confirm_order_amount(shopper, orderable):
    cart_ids = fill_cart(shopper, orderable, qty=2)
    confirm = shopper.order.generate_confirm_order(cart_ids)
    A.assert_success(confirm)
    data = A.assert_data_not_empty(confirm)

    with allure.step("确认单包含促销明细、地址、金额计算"):
        for key in ("cartPromotionItemList", "memberReceiveAddressList", "calcAmount"):
            assert key in data, f"确认单缺少 {key}"
        assert data["memberReceiveAddressList"], "确认单未带出收货地址"

    calc = data["calcAmount"]
    price = orderable["price"]
    expected_total = round(price * 2, 2)
    with allure.step(f"原价合计应为 {expected_total}（单价 {price} × 2）"):
        assert round(float(calc["totalAmount"]), 2) == expected_total, f"合计错误：{calc}"

    with allure.step("应付金额 = 原价合计 - 促销优惠，且不小于 0"):
        expect_pay = round(expected_total - float(calc["promotionAmount"]) - float(calc["freightAmount"]), 2)
        assert round(float(calc["payAmount"]), 2) == expect_pay, f"应付金额计算错误：{calc}"


@allure.story("确认单")
@allure.title("购物车为空时生成确认单失败")
@pytest.mark.xfail(reason="已知缺陷 D-13：确认单/下单未校验购物车，空购物车仍返回成功", strict=False)
@pytest.mark.case_id("MALL-POR-ORD-002")
def test_confirm_order_empty_cart(shopper):
    shopper.cart.clear()
    resp = shopper.order.generate_confirm_order([])
    A.assert_failed(resp)


@allure.story("确认单")
@allure.title("购物车 ID 不存在时生成确认单失败")
@pytest.mark.xfail(reason="已知缺陷 D-13：确认单未校验购物车 ID 是否存在，返回 200 空明细", strict=False)
@pytest.mark.case_id("MALL-POR-ORD-003")
def test_confirm_order_invalid_cart_id(shopper):
    resp = shopper.order.generate_confirm_order([99999999])
    A.assert_failed(resp)


# ---------------- 下单 ----------------
@allure.story("生成订单")
@allure.title("下单成功：订单号/状态/明细正确并落库")
@pytest.mark.smoke
@pytest.mark.case_id("MALL-POR-ORD-004")
def test_create_order_success(shopper, orderable, db):
    confirm, created, cart_ids = create_order(shopper, orderable, qty=1)

    with allure.step("响应结构：orderItemList + order"):
        assert "order" in created and "orderItemList" in created, f"下单响应结构异常：{created}"
        order = created["order"]
        assert order["orderSn"], "订单号为空"
        assert len(str(order["orderSn"])) >= 18, f"订单号长度异常：{order['orderSn']}"
        assert order["status"] == 0, f"新订单状态应为 0（待付款），实际 {order['status']}"
        assert created["orderItemList"], "订单明细为空"

    with allure.step("数据库校验：订单与明细落库，金额与确认单一致"):
        row = db.query_one("select id, order_sn, status, total_amount, pay_amount, member_id "
                           "from oms_order where id=%s", (order["id"],))
        assert row, "订单未落库"
        assert row["order_sn"] == order["orderSn"]
        assert int(row["status"]) == 0
        assert round(float(row["pay_amount"]), 2) == round(float(confirm["calcAmount"]["payAmount"]), 2), (
            f"应付金额不一致：确认单 {confirm['calcAmount']['payAmount']}，库中 {row['pay_amount']}"
        )
        item_count = db.count("oms_order_item", "order_id=%s", (order["id"],))
        assert item_count == len(created["orderItemList"]), "订单明细条数与库中不一致"


@allure.story("生成订单")
@allure.title("下单成功后锁定库存")
@pytest.mark.case_id("MALL-POR-ORD-005")
def test_create_order_locks_stock(shopper, orderable, db):
    before = db.query_one("select stock, lock_stock from pms_sku_stock where id=%s", (orderable["sku_id"],))
    create_order(shopper, orderable, qty=1)
    after = db.query_one("select stock, lock_stock from pms_sku_stock where id=%s", (orderable["sku_id"],))

    with allure.step("lock_stock 应增加 1"):
        assert int(after["lock_stock"]) == int(before["lock_stock"]) + 1, (
            f"锁定库存未增加：{before['lock_stock']} → {after['lock_stock']}"
        )
        assert int(after["stock"]) == int(before["stock"]), "下单不应直接扣减可售库存"


@allure.story("生成订单")
@allure.title("下单后购物车对应商品被清除")
@pytest.mark.case_id("MALL-POR-ORD-006")
def test_create_order_clears_cart(shopper, orderable):
    cart_ids = fill_cart(shopper, orderable)
    confirm = shopper.order.generate_confirm_order(cart_ids)
    assert confirm.code == 200
    shopper.order.generate_order({
        "memberReceiveAddressId": shopper.address_id, "couponId": None,
        "useIntegration": 0, "payType": 0, "cartIds": cart_ids,
    })
    remain = shopper.cart.list().data or []
    assert all(i["id"] not in cart_ids for i in remain), "下单后购物车未清理"


@allure.story("生成订单")
@allure.title("未登录下单被拦截")
@pytest.mark.case_id("MALL-POR-ORD-007")
def test_create_order_without_token(portal_anon, orderable, shopper):
    resp = portal_anon.post("/order/generateOrder", json_body={
        "memberReceiveAddressId": shopper.address_id, "couponId": None,
        "useIntegration": 0, "payType": 0, "cartIds": [1],
    })
    A.assert_code(resp, 401)


@allure.story("生成订单")
@allure.title("使用不属于自己的收货地址下单应失败")
@pytest.mark.security
@pytest.mark.case_id("MALL-POR-ORD-008")
def test_create_order_with_others_address(shopper, orderable, portal_member, portal_address_api):
    other_addresses = portal_address_api.list()
    cart_ids = fill_cart(shopper, orderable)
    shopper.order.generate_confirm_order(cart_ids)

    other_id = other_addresses.data[0]["id"] if other_addresses.code == 200 and other_addresses.data else None
    if other_id is None:
        pytest.skip("对照会员没有收货地址，无法构造越权场景")

    resp = shopper.order.generate_order({
        "memberReceiveAddressId": other_id, "couponId": None,
        "useIntegration": 0, "payType": 0, "cartIds": cart_ids,
    })
    assert resp.code != 200, f"使用他人地址下单成功，存在越权风险：{resp}"


@allure.story("生成订单")
@allure.title("无优惠商品下单不应报错（回归 D-06）")
@pytest.mark.xfail(reason="已知缺陷 D-06：无优惠/打折商品下单时 CartPromotionItem.price 为 null 导致 NPE", strict=False)
@pytest.mark.case_id("MALL-POR-ORD-009")
def test_create_order_no_promotion_product(shopper, sellable):
    """sellable 是「无促销」商品，正常用户也会买它，必须能下单。"""
    shopper.cart.clear()
    shopper.cart.add(sellable["product_id"], sellable["sku_id"], 1)
    cart_ids = [i["id"] for i in shopper.cart.list().data]

    confirm = shopper.order.generate_confirm_order(cart_ids)
    assert confirm.code == 200, f"确认单失败：{confirm}"

    resp = shopper.order.generate_order({
        "memberReceiveAddressId": shopper.address_id, "couponId": None,
        "useIntegration": 0, "payType": 0, "cartIds": cart_ids,
    })
    assert resp.code == 200, f"无优惠商品下单失败：{resp}"


# ---------------- 订单查询 ----------------
@allure.story("订单查询")
@allure.title("订单列表按状态筛选能查到新订单")
@pytest.mark.case_id("MALL-POR-ORD-010")
def test_order_list(shopper, orderable):
    _, created, _ = create_order(shopper, orderable)
    order_sn = created["order"]["orderSn"]

    resp = shopper.order.list(status=0)
    A.assert_success(resp)
    data = A.assert_data_not_empty(resp)
    sns = [i.get("orderSn") for i in data["list"]]
    assert order_sn in sns, f"待付款列表中未找到订单 {order_sn}，实际 {sns}"
    assert all(int(i["status"]) == 0 for i in data["list"]), "列表包含非待付款订单"


@allure.story("订单查询")
@allure.title("订单详情包含明细与金额")
@pytest.mark.case_id("MALL-POR-ORD-011")
def test_order_detail(shopper, orderable):
    confirm, created, _ = create_order(shopper, orderable)
    order_id = created["order"]["id"]

    resp = shopper.order.detail(order_id)
    A.assert_success(resp)
    data = A.assert_data_not_empty(resp)
    for key in ("id", "orderSn", "status", "totalAmount", "payAmount", "orderItemList"):
        assert key in data, f"订单详情缺少 {key}"
    assert data["orderItemList"], "订单明细为空"
    assert round(float(data["payAmount"]), 2) == round(float(confirm["calcAmount"]["payAmount"]), 2)


@allure.story("订单查询")
@allure.title("不能查看他人的订单详情（越权）")
@pytest.mark.security
@pytest.mark.xfail(reason="已知缺陷 D-11：订单详情未校验归属，可越权查看他人订单", strict=False)
@pytest.mark.case_id("MALL-POR-ORD-012")
def test_order_detail_idor(shopper, orderable, portal_order_api):
    _, created, _ = create_order(shopper, orderable)
    order_id = created["order"]["id"]

    resp = portal_order_api.detail(order_id)  # 另一个会员的客户端
    assert resp.code != 200, f"越权查看了他人订单详情：{resp}"


# ---------------- 支付 ----------------
@allure.story("支付")
@allure.title("支付成功后订单状态变为待发货")
@pytest.mark.smoke
@pytest.mark.case_id("MALL-POR-ORD-013")
def test_pay_success(shopper, orderable, db):
    _, created, _ = create_order(shopper, orderable)
    order_id = created["order"]["id"]

    resp = shopper.client.post("/order/paySuccess", params={"orderId": order_id, "payType": 0})
    A.assert_success(resp)

    row = db.query_one("select status, pay_type, payment_time from oms_order where id=%s", (order_id,))
    assert int(row["status"]) == 1, f"支付后状态应为 1（待发货），实际 {row['status']}"
    assert row["payment_time"] is not None, "支付时间未记录"


@allure.story("支付")
@allure.title("重复支付回调不应重复变更金额")
@pytest.mark.case_id("MALL-POR-ORD-014")
def test_pay_success_twice(shopper, orderable, db):
    _, created, _ = create_order(shopper, orderable)
    order_id = created["order"]["id"]

    first = shopper.client.post("/order/paySuccess", params={"orderId": order_id, "payType": 0})
    assert first.code == 200
    before = db.query_one("select status, pay_amount from oms_order where id=%s", (order_id,))

    second = shopper.client.post("/order/paySuccess", params={"orderId": order_id, "payType": 0})
    after = db.query_one("select status, pay_amount from oms_order where id=%s", (order_id,))
    assert after["pay_amount"] == before["pay_amount"], "重复支付导致金额变化"
    assert second.code != 500, f"重复支付返回服务端异常：{second}"


@allure.story("支付")
@allure.title("支付不存在的订单应失败")
@pytest.mark.case_id("MALL-POR-ORD-015")
def test_pay_success_not_exist(shopper):
    resp = shopper.client.post("/order/paySuccess", params={"orderId": 99999999, "payType": 0})
    A.assert_failed(resp)


# ---------------- 取消 / 收货 / 删除 ----------------
@allure.story("取消订单")
@allure.title("取消待付款订单后状态变为已取消且释放库存")
@pytest.mark.smoke
@pytest.mark.case_id("MALL-POR-ORD-016")
def test_cancel_order(shopper, orderable, db):
    _, created, _ = create_order(shopper, orderable)
    order_id = created["order"]["id"]
    before = db.query_one("select lock_stock from pms_sku_stock where id=%s", (orderable["sku_id"],))

    resp = shopper.order.cancel_user_order(order_id)
    A.assert_success(resp)

    row = db.query_one("select status from oms_order where id=%s", (order_id,))
    assert int(row["status"]) == 4, f"取消后状态应为 4，实际 {row['status']}"
    after = db.query_one("select lock_stock from pms_sku_stock where id=%s", (orderable["sku_id"],))
    assert int(after["lock_stock"]) == int(before["lock_stock"]) - 1, "取消订单未释放锁定库存"


@allure.story("取消订单")
@allure.title("已支付订单不能由用户取消")
@pytest.mark.xfail(reason="已知缺陷 D-09：已支付订单可被用户直接取消，无退款流程", strict=False)
@pytest.mark.case_id("MALL-POR-ORD-017")
def test_cancel_paid_order(shopper, orderable):
    _, created, _ = create_order(shopper, orderable)
    order_id = created["order"]["id"]
    shopper.client.post("/order/paySuccess", params={"orderId": order_id, "payType": 0})

    resp = shopper.order.cancel_user_order(order_id)
    assert resp.code != 200, f"已支付订单仍被用户取消：{resp}"


@allure.story("取消订单")
@allure.title("取消不存在的订单应失败")
@pytest.mark.xfail(reason="已知缺陷 D-10：取消不存在订单返回成功，未校验订单存在性", strict=False)
@pytest.mark.case_id("MALL-POR-ORD-018")
def test_cancel_not_exist_order(shopper):
    resp = shopper.order.cancel_user_order(99999999)
    A.assert_failed(resp)


@allure.story("取消订单")
@allure.title("不能取消他人订单（越权）")
@pytest.mark.security
@pytest.mark.xfail(reason="已知缺陷 D-10：可取消他人订单，cancelUserOrder 未校验会员归属", strict=False)
@pytest.mark.case_id("MALL-POR-ORD-019")
def test_cancel_others_order(shopper, orderable, portal_order_api, db):
    _, created, _ = create_order(shopper, orderable)
    order_id = created["order"]["id"]

    resp = portal_order_api.cancel_user_order(order_id)
    row = db.query_one("select status from oms_order where id=%s", (order_id,))
    if resp.code == 200:
        assert int(row["status"]) != 4, f"他人成功取消了订单 {order_id}，存在越权"
    else:
        A.assert_failed(resp)


@allure.story("确认收货")
@allure.title("未发货订单不能确认收货")
@pytest.mark.case_id("MALL-POR-ORD-020")
def test_confirm_receive_unpaid(shopper, orderable):
    _, created, _ = create_order(shopper, orderable)
    resp = shopper.client.post("/order/confirmReceiveOrder", params={"orderId": created["order"]["id"]})
    assert resp.code != 200, f"未发货订单被确认收货：{resp}"


@allure.story("删除订单")
@allure.title("已取消订单可以删除")
@pytest.mark.xfail(reason="已知缺陷 D-12：删除订单后详情仍可查询，软删除未在查询侧生效", strict=False)
@pytest.mark.case_id("MALL-POR-ORD-021")
def test_delete_cancelled_order(shopper, orderable):
    _, created, _ = create_order(shopper, orderable)
    order_id = created["order"]["id"]
    shopper.order.cancel_user_order(order_id)

    resp = shopper.client.post("/order/deleteOrder", params={"orderId": order_id})
    A.assert_success(resp)

    detail = shopper.order.detail(order_id)
    assert detail.code != 200 or detail.data is None, f"删除后仍能查到订单：{detail}"


@allure.story("超时取消")
@allure.title("无待付款订单时触发超时取消不报错")
@pytest.mark.case_id("MALL-POR-ORD-022")
def test_cancel_timeout_order(shopper):
    resp = shopper.order.cancel_timeout_order()
    assert resp.code in (200, 500), f"超时取消返回异常结构：{resp}"
    assert "Exception" not in str(resp.body)

@allure.story("生成订单")
@allure.title("空购物车下单应被拦截，且不得泄露 SQL 错误")
@pytest.mark.security
@pytest.mark.xfail(reason="已知缺陷 D-14：空购物车下单返回 500，且把 MySQL 语法错误原文返回给前端", strict=False)
@pytest.mark.case_id("MALL-POR-ORD-023")
def test_create_order_empty_cart(shopper):
    resp = shopper.order.generate_order({
        "memberReceiveAddressId": shopper.address_id, "couponId": None,
        "useIntegration": 0, "payType": 0, "cartIds": [],
    })
    assert resp.code != 500, f"空购物车下单返回 500：{resp}"
    assert "SQL" not in str(resp.body), f"响应泄露 SQL 错误：{resp.body}"
