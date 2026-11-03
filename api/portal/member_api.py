"""前台会员相关接口：收藏、浏览记录、关注、优惠券。"""
from __future__ import annotations

from typing import Any, Dict, List

from common.http_client import ApiResponse, HttpClient


class MemberCollectionApi:
    """/member/productCollection 商品收藏。"""

    def __init__(self, client: HttpClient):
        self.c = client

    def add(self, product: Dict[str, Any]) -> ApiResponse:
        return self.c.post("/member/productCollection/add", json_body=product)

    def list(self, page_num: int = 1, page_size: int = 10) -> ApiResponse:
        return self.c.get("/member/productCollection/list", params={"pageNum": page_num, "pageSize": page_size})

    def detail(self, product_id: int) -> ApiResponse:
        return self.c.get("/member/productCollection/detail", params={"productId": product_id})

    def delete(self, product_id: int) -> ApiResponse:
        return self.c.post("/member/productCollection/delete", params={"productId": product_id})

    def clear(self) -> ApiResponse:
        return self.c.post("/member/productCollection/clear")


class MemberReadHistoryApi:
    """/member/readHistory 浏览记录。"""

    def __init__(self, client: HttpClient):
        self.c = client

    def create(self, product: Dict[str, Any]) -> ApiResponse:
        return self.c.post("/member/readHistory/create", json_body=product)

    def list(self, page_num: int = 1, page_size: int = 10) -> ApiResponse:
        return self.c.get("/member/readHistory/list", params={"pageNum": page_num, "pageSize": page_size})

    def clear(self) -> ApiResponse:
        return self.c.post("/member/readHistory/clear")

    def delete(self, ids: List[str]) -> ApiResponse:
        return self.c.post("/member/readHistory/delete", params={"ids": ",".join(ids)})


class MemberAttentionApi:
    """/member/attention 品牌关注。"""

    def __init__(self, client: HttpClient):
        self.c = client

    def add(self, brand: Dict[str, Any]) -> ApiResponse:
        return self.c.post("/member/attention/add", json_body=brand)

    def list(self) -> ApiResponse:
        return self.c.get("/member/attention/list")

    def detail(self, brand_id: int) -> ApiResponse:
        return self.c.get("/member/attention/detail", params={"brandId": brand_id})

    def delete(self, brand_id: int) -> ApiResponse:
        return self.c.post("/member/attention/delete", params={"brandId": brand_id})

    def clear(self) -> ApiResponse:
        return self.c.post("/member/attention/clear")


class MemberCouponApi:
    """/member/coupon 优惠券。"""

    def __init__(self, client: HttpClient):
        self.c = client

    def add(self, coupon_id: int) -> ApiResponse:
        return self.c.post(f"/member/coupon/add/{coupon_id}")

    def list(self, use_status: int | None = None) -> ApiResponse:
        return self.c.get("/member/coupon/list", params={"useStatus": use_status} if use_status is not None else None)

    def list_history(self, use_status: int | None = None) -> ApiResponse:
        return self.c.get("/member/coupon/listHistory",
                          params={"useStatus": use_status} if use_status is not None else None)

    def list_cart(self, type_: int = 0) -> ApiResponse:
        return self.c.get(f"/member/coupon/list/cart/{type_}")

    def list_by_product(self, product_id: int) -> ApiResponse:
        return self.c.get(f"/member/coupon/listByProduct/{product_id}")
