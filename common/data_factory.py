"""测试数据工厂：保证用例数据唯一、可复现、不互相污染。

核心约定：
- 手机号/用户名运行时生成（时间戳 + 自增），重复执行不会撞「已注册」；
- 商品与 SKU 不写死，从商品详情接口实时取，环境换库也不失效；
- 收货地址按 mall 的省市区格式构造。
"""
from __future__ import annotations

import itertools
import time
from typing import Any, Dict, Tuple

from common.http_client import HttpClient
from common.logger import get_logger

log = get_logger("data")

_seq = itertools.count(1)

DEFAULT_PASSWORD = "Test@1234"


def _suffix() -> str:
    """8 位唯一后缀：时间戳后 6 位 + 自增 2 位。"""
    n = next(_seq) % 100
    return f"{int(time.time()) % 1000000:06d}{n:02d}"


def unique_phone(prefix: str = "139") -> str:
    """生成唯一手机号（11 位，139 + 8 位）。"""
    return f"{prefix}{_suffix()}"


def unique_username(prefix: str = "auto_") -> str:
    return f"{prefix}{_suffix()}"


def get_product_detail(client: HttpClient, product_id: int = 1) -> Dict[str, Any]:
    """取商品详情（product + skuStockList）。"""
    resp = client.get(f"/product/detail/{product_id}")
    assert resp.code == 200, f"商品详情查询失败：{resp}"
    data = resp.data or {}
    assert data.get("product"), f"商品 {product_id} 不存在或已下架"
    return data


def pick_sellable_sku(detail: Dict[str, Any]) -> Tuple[int, int]:
    """从详情里挑一个可售 SKU，返回 (skuId, stock)。"""
    skus = detail.get("skuStockList") or []
    for sku in skus:
        if int(sku.get("stock") or 0) > 0:
            return int(sku["id"]), int(sku["stock"])
    raise AssertionError(f"商品 {detail.get('product', {}).get('id')} 无可售 SKU，库存数据：{skus}")


def build_address() -> Dict[str, Any]:
    """构造一条收货地址（mall 使用省市区中文名 + 详细地址）。"""
    return {
        "name": "自动化测试",
        "phoneNumber": "13800000000",
        "defaultStatus": 1,
        "postCode": "518000",
        "province": "广东省",
        "city": "深圳市",
        "region": "南山区",
        "detailAddress": f"科技园路{next(_seq)}号",
    }


def member_account() -> Dict[str, str]:
    """一个待注册的会员账号信息。"""
    return {
        "username": unique_username(),
        "password": DEFAULT_PASSWORD,
        "telephone": unique_phone(),
    }
