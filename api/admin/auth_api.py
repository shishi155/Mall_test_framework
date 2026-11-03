"""后台登录认证接口封装（商品/订单见 admin_api.py）。"""
from __future__ import annotations

from common.http_client import ApiResponse, HttpClient


class AdminAuthApi:
    def __init__(self, client: HttpClient):
        self.c = client

    def login(self, username: str, password: str) -> ApiResponse:
        return self.c.post("/admin/login", json_body={"username": username, "password": password})

    def register(self, payload: dict) -> ApiResponse:
        return self.c.post("/admin/register", json_body=payload)

    def info(self) -> ApiResponse:
        return self.c.get("/admin/info")

    def list_admins(self, keyword: str | None = None, page_num: int = 1, page_size: int = 5) -> ApiResponse:
        params = {"pageNum": page_num, "pageSize": page_size}
        if keyword:
            params["keyword"] = keyword
        return self.c.get("/admin/list", params=params)

    def logout(self) -> ApiResponse:
        return self.c.post("/admin/logout")

    def roles(self, admin_id: int) -> ApiResponse:
        return self.c.get(f"/admin/role/{admin_id}")

    def update_roles(self, admin_id: int, role_ids: list[int]) -> ApiResponse:
        return self.c.post("/admin/role/update",
                           params={"adminId": admin_id, "roleIds": ",".join(map(str, role_ids))})
