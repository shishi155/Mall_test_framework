"""前台（mall-portal）接口封装。

注意：Sso 相关接口使用 @RequestParam（表单/查询参数），不是 JSON。
"""
from __future__ import annotations

from typing import Any, Dict, List

from common.http_client import ApiResponse, HttpClient


class PortalSsoApi:
    def __init__(self, client: HttpClient):
        self.c = client

    def get_auth_code(self, telephone: str) -> ApiResponse:
        return self.c.get("/sso/getAuthCode", params={"telephone": telephone})

    def register(self, username: str, password: str, telephone: str, auth_code: str) -> ApiResponse:
        return self.c.post("/sso/register", data={
            "username": username, "password": password,
            "telephone": telephone, "authCode": auth_code,
        })

    def login(self, username: str, password: str) -> ApiResponse:
        return self.c.post("/sso/login", data={"username": username, "password": password})

    def info(self) -> ApiResponse:
        return self.c.get("/sso/info")

    def refresh_token(self) -> ApiResponse:
        return self.c.get("/sso/refreshToken")

    def update_password(self, telephone: str, password: str, auth_code: str) -> ApiResponse:
        return self.c.post("/sso/updatePassword", data={
            "telephone": telephone, "password": password, "authCode": auth_code,
        })


class PortalHomeApi:
    def __init__(self, client: HttpClient):
        self.c = client

    def content(self) -> ApiResponse:
        return self.c.get("/home/content")

    def recommend_product_list(self) -> ApiResponse:
        return self.c.get("/home/recommendProductList", params={"pageSize": 5})

    def hot_product_list(self) -> ApiResponse:
        return self.c.get("/home/hotProductList", params={"pageSize": 5})

    def new_product_list(self) -> ApiResponse:
        return self.c.get("/home/newProductList", params={"pageSize": 5})


class PortalProductApi:
    def __init__(self, client: HttpClient):
        self.c = client

    def detail(self, product_id: int) -> ApiResponse:
        return self.c.get(f"/product/detail/{product_id}")

    def search(self, keyword: str = "", page_num: int = 1, page_size: int = 5) -> ApiResponse:
        return self.c.get("/product/search", params={
            "keyword": keyword, "pageNum": page_num, "pageSize": page_size,
        })

    def category_tree(self) -> ApiResponse:
        return self.c.get("/product/categoryTreeList")


class PortalCartApi:
    def __init__(self, client: HttpClient):
        self.c = client

    def add(self, product_id: int, sku_id: int, quantity: int = 1) -> ApiResponse:
        return self.c.post("/cart/add", json_body={
            "productId": product_id, "productSkuId": sku_id, "quantity": quantity,
        })

    def list(self) -> ApiResponse:
        return self.c.get("/cart/list")

    def list_promotion(self, cart_ids: List[int] | None = None) -> ApiResponse:
        return self.c.get("/cart/list/promotion", params={"cartIds": cart_ids} if cart_ids else None)

    def update_quantity(self, cart_item_id: int, quantity: int) -> ApiResponse:
        return self.c.get("/cart/update/quantity", params={"id": cart_item_id, "quantity": quantity})

    def get_product(self, product_id: int) -> ApiResponse:
        """取购物车中的商品信息（含价格、库存），/cart/list 不返回这些字段。"""
        return self.c.get(f"/cart/getProduct/{product_id}")

    def delete(self, ids: List[int]) -> ApiResponse:
        return self.c.post("/cart/delete", params={"ids": ",".join(map(str, ids))})

    def clear(self) -> ApiResponse:
        return self.c.post("/cart/clear")


class PortalOrderApi:
    def __init__(self, client: HttpClient):
        self.c = client

    def generate_confirm_order(self, cart_ids: List[int]) -> ApiResponse:
        return self.c.post("/order/generateConfirmOrder", json_body=cart_ids)

    def generate_order(self, order_param: Dict[str, Any]) -> ApiResponse:
        return self.c.post("/order/generateOrder", json_body=order_param)

    def list(self, status: int | None = None, page_num: int = 1, page_size: int = 5) -> ApiResponse:
        return self.c.get("/order/list", params={"status": status, "pageNum": page_num, "pageSize": page_size})

    def detail(self, order_id: int) -> ApiResponse:
        return self.c.get(f"/order/detail/{order_id}")

    def cancel_user_order(self, order_id: int) -> ApiResponse:
        return self.c.post("/order/cancelUserOrder", params={"orderId": order_id})

    def cancel_timeout_order(self) -> ApiResponse:
        return self.c.post("/order/cancelTimeOutOrder")


class PortalAddressApi:
    def __init__(self, client: HttpClient):
        self.c = client

    def add(self, address: Dict[str, Any]) -> ApiResponse:
        return self.c.post("/member/address/add", json_body=address)

    def list(self) -> ApiResponse:
        return self.c.get("/member/address/list")

    def get(self, address_id: int) -> ApiResponse:
        return self.c.get(f"/member/address/{address_id}")

    def update(self, address_id: int, address: Dict[str, Any]) -> ApiResponse:
        return self.c.post(f"/member/address/update/{address_id}", json_body=address)

    def delete(self, address_id: int) -> ApiResponse:
        return self.c.post(f"/member/address/delete/{address_id}")
