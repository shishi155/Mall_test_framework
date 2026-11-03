"""下单链路辅助函数：前台测试与后台测试共用（避免跨测试模块 import）。"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple


def fill_cart(shopper, orderable: Dict[str, Any], qty: int = 1) -> List[int]:
    """清空购物车 → 加购 → 返回 cartIds。"""
    shopper.cart.clear()
    resp = shopper.cart.add(orderable["product_id"], orderable["sku_id"], qty)
    assert resp.code == 200, f"加购失败：{resp}"
    cart_ids = [i["id"] for i in shopper.cart.list().data]
    assert cart_ids, "加购后购物车为空"
    return cart_ids


def create_order(shopper, orderable: Dict[str, Any], qty: int = 1
                 ) -> Tuple[Dict[str, Any], Dict[str, Any], List[int]]:
    """走完「确认单 → 下单」，返回 (确认单数据, 下单数据, cartIds)。"""
    cart_ids = fill_cart(shopper, orderable, qty)
    confirm = shopper.order.generate_confirm_order(cart_ids)
    assert confirm.code == 200, f"确认单失败：{confirm}"

    param = {
        "memberReceiveAddressId": shopper.address_id,
        "couponId": None,
        "useIntegration": 0,
        "payType": 0,
        "cartIds": cart_ids,
    }
    created = shopper.order.generate_order(param)
    assert created.code == 200, f"下单失败：{created}"
    return confirm.data, created.data, cart_ids
