"""pytest 全局夹具。

分层：
  settings        会话级配置
  admin_anon      未登录的后台客户端
  admin_client    已登录的后台客户端（token 自动注入）
  portal_member   会话级会员账号（唯一手机号，运行时注册）
  portal_client   已登录的前台客户端
  db              直连测试库，用于数据一致性断言
  clean_cart      函数级购物车清理
"""
from __future__ import annotations

import allure
import pytest

from api.admin.admin_api import (
    AdminBaseApi, AdminMarketingApi, AdminOrderApi, AdminProductApi, AdminRoleApi,
)
from api.admin.auth_api import AdminAuthApi
from api.portal.member_api import (
    MemberAttentionApi, MemberCollectionApi, MemberCouponApi, MemberReadHistoryApi,
)
from api.portal.sso_api import (
    PortalAddressApi, PortalCartApi, PortalHomeApi, PortalOrderApi, PortalProductApi, PortalSsoApi,
)
from api.registry import ApiContext
from common import data_factory
from common.db import DB
from common.http_client import HttpClient
from common.logger import get_logger
from config.settings import Settings, load_settings

log = get_logger("conftest")


def pytest_addoption(parser):
    parser.addoption("--env", action="store", default=None, help="运行环境：local / ci")


def pytest_configure(config):
    config.addinivalue_line("markers", "smoke: 冒烟用例，每次提交必跑")
    config.addinivalue_line("markers", "regression: 回归用例")
    config.addinivalue_line("markers", "security: 安全专项用例")
    config.addinivalue_line("markers", "perf: 性能相关")
    config.addinivalue_line("markers", "point: 单接口校验点用例（可由 Excel 驱动）")
    config.addinivalue_line("markers", "link: 业务链路用例")
    config.addinivalue_line("markers", "case_id: 关联 Excel 用例编号")


@pytest.fixture(scope="session")
def settings(request) -> Settings:
    s = load_settings(request.config.getoption("--env"))
    log.info("环境=%s(%s) admin=%s portal=%s", s.env, s.name, s.admin.base_url, s.portal.base_url)
    return s


@pytest.fixture(scope="session", autouse=True)
def allure_environment(settings):
    """把环境信息写进 Allure 报告。"""
    d = settings.allure_results_dir()
    lines = [
        f"Environment={settings.env} ({settings.name})",
        f"mall-admin={settings.admin.base_url}",
        f"mall-portal={settings.portal.base_url}",
        f"mall-admin-web={settings.web.base_url}",
        f"MySQL={settings.db.host}:{settings.db.port}/{settings.db.database}",
        "Python=" + __import__("sys").version.split()[0],
    ]
    (d / "environment.properties").write_text("\n".join(lines), encoding="utf-8")


# ---------------- 后台 ----------------
@pytest.fixture(scope="session")
def admin_anon(settings) -> HttpClient:
    return HttpClient(settings.admin.base_url, settings.admin.timeout, "admin-anon")


@pytest.fixture(scope="session")
def admin_token(settings, admin_anon) -> str:
    acc = settings.admin_account
    resp = AdminAuthApi(admin_anon).login(acc["username"], acc["password"])
    assert resp.code == 200, f"后台登录失败，无法继续：{resp}"
    token = resp.data["token"]
    log.info("后台 token 获取成功")
    return token


@pytest.fixture(scope="session")
def admin_client(settings, admin_token) -> HttpClient:
    return HttpClient(settings.admin.base_url, settings.admin.timeout, "admin").set_token(admin_token)


@pytest.fixture(scope="session")
def admin_auth_api(admin_anon) -> AdminAuthApi:
    return AdminAuthApi(admin_anon)


@pytest.fixture(scope="session")
def admin_product_api(admin_client) -> AdminProductApi:
    return AdminProductApi(admin_client)


@pytest.fixture(scope="session")
def admin_order_api(admin_client) -> AdminOrderApi:
    return AdminOrderApi(admin_client)


# ---------------- 前台 ----------------
@pytest.fixture(scope="session")
def portal_anon(settings) -> HttpClient:
    return HttpClient(settings.portal.base_url, settings.portal.timeout, "portal-anon")


@pytest.fixture(scope="session")
def portal_sso_api(portal_anon) -> PortalSsoApi:
    return PortalSsoApi(portal_anon)


@pytest.fixture(scope="session")
def portal_member(portal_sso_api) -> dict:
    """注册一个专属会员，返回账号信息（含 token）。"""
    acc = data_factory.member_account()
    code_resp = portal_sso_api.get_auth_code(acc["telephone"])
    assert code_resp.code == 200, f"获取验证码失败：{code_resp}"
    resp = portal_sso_api.register(acc["username"], acc["password"], acc["telephone"], code_resp.data)
    assert resp.code == 200, f"注册会员失败：{resp}"

    login = portal_sso_api.login(acc["username"], acc["password"])
    assert login.code == 200, f"会员登录失败：{login}"
    acc["token"] = login.data["token"]
    acc["token_head"] = login.data.get("tokenHead", "Bearer ")
    log.info("前台会员注册并登录成功：%s", acc["username"])
    return acc


@pytest.fixture(scope="session")
def portal_client(settings, portal_member) -> HttpClient:
    return HttpClient(settings.portal.base_url, settings.portal.timeout, "portal").set_token(portal_member["token"])


@pytest.fixture(scope="session")
def portal_product_api(portal_client) -> PortalProductApi:
    return PortalProductApi(portal_client)


@pytest.fixture(scope="session")
def portal_cart_api(portal_client) -> PortalCartApi:
    return PortalCartApi(portal_client)


@pytest.fixture(scope="session")
def portal_order_api(portal_client) -> PortalOrderApi:
    return PortalOrderApi(portal_client)


@pytest.fixture(scope="session")
def portal_home_api(portal_client) -> PortalHomeApi:
    return PortalHomeApi(portal_client)


@pytest.fixture(scope="session")
def portal_address_api(portal_client) -> PortalAddressApi:
    return PortalAddressApi(portal_client)


@pytest.fixture()
def clean_cart(portal_cart_api):
    """用例前后都清空购物车，避免历史数据干扰断言。"""
    portal_cart_api.clear()
    yield
    portal_cart_api.clear()


@pytest.fixture(scope="session")
def member_collection_api(portal_client) -> MemberCollectionApi:
    return MemberCollectionApi(portal_client)


@pytest.fixture(scope="session")
def member_history_api(portal_client) -> MemberReadHistoryApi:
    return MemberReadHistoryApi(portal_client)


@pytest.fixture(scope="session")
def member_attention_api(portal_client) -> MemberAttentionApi:
    return MemberAttentionApi(portal_client)


@pytest.fixture(scope="session")
def member_coupon_api(portal_client) -> MemberCouponApi:
    return MemberCouponApi(portal_client)


# ---------------- 后台业务接口 ----------------
@pytest.fixture(scope="session")
def admin_role_api(admin_client) -> AdminRoleApi:
    return AdminRoleApi(admin_client)


@pytest.fixture(scope="session")
def admin_marketing_api(admin_client) -> AdminMarketingApi:
    return AdminMarketingApi(admin_client)


@pytest.fixture(scope="session")
def admin_base_api(admin_client) -> AdminBaseApi:
    return AdminBaseApi(admin_client)


# ---------------- 业务专用账号 ----------------
@pytest.fixture()
def shopper(settings, portal_anon):
    """下单链路专用：函数级独立会员 + 默认收货地址，用例之间互不干扰。"""
    sso = PortalSsoApi(portal_anon)
    acc = data_factory.member_account()
    code = sso.get_auth_code(acc["telephone"]).data
    reg = sso.register(acc["username"], acc["password"], acc["telephone"], code)
    assert reg.code == 200, f"shopper 注册失败：{reg}"

    login = sso.login(acc["username"], acc["password"])
    assert login.code == 200, f"shopper 登录失败：{login}"

    client = HttpClient(settings.portal.base_url, settings.portal.timeout, "shopper").set_token(login.data["token"])
    address_api = PortalAddressApi(client)
    addr = data_factory.build_address()
    assert address_api.add(addr).code == 200, "shopper 添加收货地址失败"
    address_id = address_api.list().data[0]["id"]

    from types import SimpleNamespace
    return SimpleNamespace(
        account=acc,
        client=client,
        sso=PortalSsoApi(client),
        cart=PortalCartApi(client),
        order=PortalOrderApi(client),
        address=address_api,
        address_id=address_id,
        address_payload=addr,
    )


# ---------------- 数据与上下文 ----------------
@pytest.fixture(scope="session")
def db(settings):
    d = DB(settings.db).connect()
    yield d
    d.close()


@pytest.fixture(scope="session")
def sellable(db) -> dict:
    """从数据库取一个「已上架 + 有库存」的商品与 SKU。

    不写死商品 id：mall.sql 里 id=1 的商品 delete_status=1（已删除）且无 SKU，
    写死会导致加购/下单用例假失败。
    """
    row = db.query_one(
        "select s.product_id, s.id as sku_id, s.stock, s.price "
        "from pms_sku_stock s join pms_product p on p.id = s.product_id "
        "where s.stock > 0 and p.delete_status = 0 and p.publish_status = 1 "
        "order by s.id limit 1"
    )
    assert row, "数据库中没有可售商品/SKU，请先初始化 mall.sql"
    log.info("选中可售商品 productId=%s skuId=%s stock=%s", row["product_id"], row["sku_id"], row["stock"])
    return {
        "product_id": int(row["product_id"]),
        "sku_id": int(row["sku_id"]),
        "stock": int(row["stock"]),
        "price": float(row["price"]),
    }


@pytest.fixture(scope="session")
def orderable(db) -> dict:
    """可下单商品：mall-portal 的优惠计算对「无优惠/打折/满减」商品会 NPE（缺陷 D-06），
    因此下单链路必须用 promotion_type=1（单品促销）且 price/promotion_price 均不为空的 SKU。"""
    row = db.query_one(
        "select s.product_id, s.id as sku_id, s.stock, s.price, s.promotion_price, p.name "
        "from pms_sku_stock s join pms_product p on p.id = s.product_id "
        "where p.promotion_type = 1 and p.delete_status = 0 and p.publish_status = 1 "
        "and s.stock - s.lock_stock > 0 and s.price is not null and s.promotion_price is not null "
        "order by s.id limit 1"
    )
    assert row, "数据库中没有可下单商品（promotion_type=1 且有促销价），请检查 mall.sql 数据"
    log.info("选中可下单商品 productId=%s skuId=%s", row["product_id"], row["sku_id"])
    return {
        "product_id": int(row["product_id"]),
        "sku_id": int(row["sku_id"]),
        "stock": int(row["stock"]),
        "price": float(row["price"]),
        "promotion_price": float(row["promotion_price"]),
        "name": row["name"],
    }


@pytest.fixture(scope="session")
def ctx_factory(settings, admin_token, portal_member):
    """按需构造 ApiContext（是否带 token），供 Excel 驱动用例使用。"""
    cache: dict[bool, ApiContext] = {}

    def make(with_token: bool = True) -> ApiContext:
        if with_token not in cache:
            admin = HttpClient(settings.admin.base_url, settings.admin.timeout, "admin").set_token(admin_token)
            portal = HttpClient(settings.portal.base_url, settings.portal.timeout, "portal").set_token(portal_member["token"])
            anon_admin = HttpClient(settings.admin.base_url, settings.admin.timeout, "admin-anon")
            anon_portal = HttpClient(settings.portal.base_url, settings.portal.timeout, "portal-anon")
            if with_token:
                cache[with_token] = ApiContext(admin=admin, portal=portal,
                                               anonymous_admin=anon_admin, anonymous_portal=anon_portal)
            else:
                cache[with_token] = ApiContext(admin=anon_admin, portal=anon_portal,
                                               anonymous_admin=anon_admin, anonymous_portal=anon_portal)
        return cache[with_token]

    return make


def pytest_runtest_call(item):
    """用例执行前，把 Excel 用例编号写进 Allure 的 title 前缀，便于追溯。"""
    marker = item.get_closest_marker("case_id")
    if marker and marker.args:
        allure.dynamic.label("case_id", str(marker.args[0]))
