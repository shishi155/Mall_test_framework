"""接口注册表：把 Excel「参数化数据」里的接口标识映射到真实调用。

约定：
- key 形如 admin.login / portal.cart.add，前缀决定用哪个服务客户端；
- 签名统一为 fn(ctx, params) -> ApiResponse；
- 新增接口只需 @register("xxx.yyy") 一行，Excel 里就能直接引用。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict

from common.http_client import ApiResponse, HttpClient


@dataclass
class ApiContext:
    """执行上下文：按服务提供的已鉴权客户端。"""
    admin: HttpClient
    portal: HttpClient
    anonymous_admin: HttpClient
    anonymous_portal: HttpClient


REGISTRY: Dict[str, Callable[[ApiContext, Dict[str, Any]], ApiResponse]] = {}


def register(key: str):
    def deco(fn):
        REGISTRY[key] = fn
        return fn
    return deco


# ---------------- 后台 ----------------
@register("admin.login")
def _(ctx: ApiContext, p: Dict[str, Any]) -> ApiResponse:
    return ctx.anonymous_admin.post("/admin/login", json_body=p)


@register("admin.info")
def _(ctx: ApiContext, p: Dict[str, Any]) -> ApiResponse:
    return ctx.admin.get("/admin/info")


@register("admin.list")
def _(ctx: ApiContext, p: Dict[str, Any]) -> ApiResponse:
    return ctx.admin.get("/admin/list", params=p or {"pageNum": 1, "pageSize": 5})


@register("admin.product.list")
def _(ctx: ApiContext, p: Dict[str, Any]) -> ApiResponse:
    return ctx.admin.get("/product/list", params=p or {"pageNum": 1, "pageSize": 5})


# ---------------- 前台 ----------------
@register("portal.authCode")
def _(ctx: ApiContext, p: Dict[str, Any]) -> ApiResponse:
    return ctx.anonymous_portal.get("/sso/getAuthCode", params=p)


@register("portal.sso.login")
def _(ctx: ApiContext, p: Dict[str, Any]) -> ApiResponse:
    return ctx.anonymous_portal.post("/sso/login", data=p)


@register("portal.home.content")
def _(ctx: ApiContext, p: Dict[str, Any]) -> ApiResponse:
    return ctx.anonymous_portal.get("/home/content")


@register("portal.product.detail")
def _(ctx: ApiContext, p: Dict[str, Any]) -> ApiResponse:
    params = dict(p or {})
    product_id = params.pop("id", 1)
    return ctx.anonymous_portal.get(f"/product/detail/{product_id}", params=params or None)


@register("portal.product.search")
def _(ctx: ApiContext, p: Dict[str, Any]) -> ApiResponse:
    return ctx.anonymous_portal.get("/product/search", params=p or {"keyword": "手机"})


@register("portal.cart.add")
def _(ctx: ApiContext, p: Dict[str, Any]) -> ApiResponse:
    return ctx.portal.post("/cart/add", json_body=p)


@register("portal.cart.list")
def _(ctx: ApiContext, p: Dict[str, Any]) -> ApiResponse:
    return ctx.portal.get("/cart/list")


@register("portal.order.list")
def _(ctx: ApiContext, p: Dict[str, Any]) -> ApiResponse:
    return ctx.portal.get("/order/list", params=p or {"status": 0})
