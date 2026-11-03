"""后台接口封装（商品 / 订单 / 角色权限 / 营销 / 基础数据）。"""
from __future__ import annotations

from typing import Any, Dict, List

from common.http_client import ApiResponse, HttpClient


class AdminProductApi:
    """商品管理。注：本类同时供 api/admin/auth_api.py 中同名类复用（避免重复导入）。"""

    def __init__(self, client: HttpClient):
        self.c = client

    # ---- 查询 ----
    def list(self, keyword: str | None = None, page_num: int = 1, page_size: int = 5,
             publish_status: int | None = None, verify_status: int | None = None) -> ApiResponse:
        params: Dict[str, Any] = {"pageNum": page_num, "pageSize": page_size}
        if keyword:
            params["keyword"] = keyword
        if publish_status is not None:
            params["publishStatus"] = publish_status
        if verify_status is not None:
            params["verifyStatus"] = verify_status
        return self.c.get("/product/list", params=params)

    def simple_list(self, keyword: str | None = None) -> ApiResponse:
        return self.c.get("/product/simpleList", params={"keyword": keyword} if keyword else None)

    def update_info(self, product_id: int) -> ApiResponse:
        return self.c.get(f"/product/updateInfo/{product_id}")

    # ---- 状态类操作 ----
    def update_publish_status(self, ids: List[int], publish_status: int) -> ApiResponse:
        return self.c.post("/product/update/publishStatus", params={"ids": ",".join(map(str, ids)),
                                                                   "publishStatus": publish_status})

    def update_verify_status(self, ids: List[int], verify_status: int, detail: str = "") -> ApiResponse:
        return self.c.post("/product/update/verifyStatus", params={"ids": ",".join(map(str, ids)),
                                                                   "verifyStatus": verify_status, "detail": detail})

    def update_recommend_status(self, ids: List[int], recommend_status: int) -> ApiResponse:
        return self.c.post("/product/update/recommendStatus", params={"ids": ",".join(map(str, ids)),
                                                                      "recommendStatus": recommend_status})

    def update_new_status(self, ids: List[int], new_status: int) -> ApiResponse:
        return self.c.post("/product/update/newStatus", params={"ids": ",".join(map(str, ids)),
                                                                "newStatus": new_status})

    def update_delete_status(self, ids: List[int], delete_status: int) -> ApiResponse:
        return self.c.post("/product/update/deleteStatus", params={"ids": ",".join(map(str, ids)),
                                                                   "deleteStatus": delete_status})

    def update(self, product_id: int, payload: Dict[str, Any]) -> ApiResponse:
        return self.c.post(f"/product/update/{product_id}", json_body=payload)


class AdminOrderApi:
    """订单管理。"""

    def __init__(self, client: HttpClient):
        self.c = client

    def list(self, status: int | None = None, order_sn: str | None = None,
             page_num: int = 1, page_size: int = 5) -> ApiResponse:
        params: Dict[str, Any] = {"pageNum": page_num, "pageSize": page_size}
        if status is not None:
            params["status"] = status
        if order_sn:
            params["orderSn"] = order_sn
        return self.c.get("/order/list", params=params)

    def detail(self, order_id: int) -> ApiResponse:
        return self.c.get(f"/order/{order_id}")

    def delivery(self, items: List[Dict[str, Any]]) -> ApiResponse:
        return self.c.post("/order/update/delivery", json_body=items)

    def close(self, ids: List[int], note: str = "测试关闭") -> ApiResponse:
        return self.c.post("/order/update/close", params={"ids": ",".join(map(str, ids)), "note": note})

    def delete(self, ids: List[int]) -> ApiResponse:
        return self.c.post("/order/delete", params={"ids": ",".join(map(str, ids))})

    def update_receiver_info(self, payload: Dict[str, Any]) -> ApiResponse:
        return self.c.post("/order/update/receiverInfo", json_body=payload)

    def update_money_info(self, payload: Dict[str, Any]) -> ApiResponse:
        return self.c.post("/order/update/moneyInfo", json_body=payload)

    def update_note(self, order_id: int, note: str, status: int = 0) -> ApiResponse:
        return self.c.post("/order/update/note", params={"id": order_id, "note": note, "status": status})


class AdminRoleApi:
    """角色与资源分配（RBAC）。"""

    def __init__(self, client: HttpClient):
        self.c = client

    def create(self, role: Dict[str, Any]) -> ApiResponse:
        return self.c.post("/role/create", json_body=role)

    def update(self, role_id: int, role: Dict[str, Any]) -> ApiResponse:
        return self.c.post(f"/role/update/{role_id}", json_body=role)

    def delete(self, ids: List[int]) -> ApiResponse:
        return self.c.post("/role/delete", params={"ids": ",".join(map(str, ids))})

    def list_all(self) -> ApiResponse:
        return self.c.get("/role/listAll")

    def list(self, keyword: str | None = None, page_num: int = 1, page_size: int = 10) -> ApiResponse:
        params: Dict[str, Any] = {"pageNum": page_num, "pageSize": page_size}
        if keyword:
            params["keyword"] = keyword
        return self.c.get("/role/list", params=params)

    def update_status(self, role_id: int, status: int) -> ApiResponse:
        return self.c.post(f"/role/updateStatus/{role_id}", params={"status": status})

    def list_menu(self, role_id: int) -> ApiResponse:
        return self.c.get(f"/role/listMenu/{role_id}")

    def list_resource(self, role_id: int) -> ApiResponse:
        return self.c.get(f"/role/listResource/{role_id}")

    def alloc_menu(self, role_id: int, menu_ids: List[int]) -> ApiResponse:
        return self.c.post("/role/allocMenu", params={"roleId": role_id, "menuIds": ",".join(map(str, menu_ids))})

    def alloc_resource(self, role_id: int, resource_ids: List[int]) -> ApiResponse:
        return self.c.post("/role/allocResource",
                           params={"roleId": role_id, "resourceIds": ",".join(map(str, resource_ids))})


class AdminMarketingApi:
    """营销：优惠券 / 秒杀 / 首页运营。"""

    def __init__(self, client: HttpClient):
        self.c = client

    # 优惠券
    def coupon_list(self, name: str | None = None, page_num: int = 1, page_size: int = 5) -> ApiResponse:
        params: Dict[str, Any] = {"pageNum": page_num, "pageSize": page_size}
        if name:
            params["name"] = name
        return self.c.get("/coupon/list", params=params)

    def coupon_detail(self, coupon_id: int) -> ApiResponse:
        return self.c.get(f"/coupon/{coupon_id}")

    def coupon_create(self, payload: Dict[str, Any]) -> ApiResponse:
        return self.c.post("/coupon/create", json_body=payload)

    def coupon_delete(self, coupon_id: int) -> ApiResponse:
        return self.c.post(f"/coupon/delete/{coupon_id}")

    # 秒杀场次
    def flash_session_list(self) -> ApiResponse:
        return self.c.get("/flashSession/list")

    def flash_list(self) -> ApiResponse:
        return self.c.get("/flash/list")

    # 首页广告
    def advertise_list(self, page_num: int = 1, page_size: int = 5) -> ApiResponse:
        return self.c.get("/home/advertise/list", params={"pageNum": page_num, "pageSize": page_size})


class AdminBaseApi:
    """基础数据：会员等级、公司地址、专题、偏好专区、订单设置、退货原因。"""

    def __init__(self, client: HttpClient):
        self.c = client

    def member_level_list(self) -> ApiResponse:
        return self.c.get("/memberLevel/list", params={"defaultStatus": 0})

    def company_address_list(self) -> ApiResponse:
        return self.c.get("/companyAddress/list")

    def subject_list(self) -> ApiResponse:
        return self.c.get("/subject/listAll")

    def prefrence_area_list(self) -> ApiResponse:
        return self.c.get("/prefrenceArea/listAll")

    def order_setting(self, setting_id: int = 1) -> ApiResponse:
        return self.c.get(f"/orderSetting/{setting_id}")

    def return_reason_list(self, page_num: int = 1, page_size: int = 5) -> ApiResponse:
        return self.c.get("/returnReason/list", params={"pageNum": page_num, "pageSize": page_size})
