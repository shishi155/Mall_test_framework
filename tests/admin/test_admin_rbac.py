"""后台角色与权限（RBAC）（MALL-ADM-RBAC-*）。"""
from __future__ import annotations

import allure
import pytest

from common import assertions as A
from common import data_factory
from common.http_client import HttpClient

pytestmark = [
    pytest.mark.regression,
    allure.epic("mall 商城"),
    allure.feature("后台-角色权限"),
]


@pytest.fixture()
def temp_role(admin_role_api, db):
    """创建一个临时角色，用例结束删除。"""
    name = f"auto_role_{data_factory.unique_username(prefix='')}"
    resp = admin_role_api.create({"name": name, "description": "自动化测试角色", "adminCount": 0, "status": 1, "sort": 0})
    A.assert_success(resp)

    row = db.query_one("select id from ums_role where name=%s order by id desc limit 1", (name,))
    assert row, "角色未落库"
    yield {"id": int(row["id"]), "name": name}
    admin_role_api.delete([int(row["id"])])


@allure.story("角色列表")
@allure.title("角色列表与全量列表可查询")
@pytest.mark.case_id("MALL-ADM-RBAC-001")
def test_role_list(admin_role_api):
    page = admin_role_api.list(page_size=10)
    A.assert_success(page)
    assert isinstance(page.data.get("list"), list)

    all_roles = admin_role_api.list_all()
    A.assert_success(all_roles)
    assert isinstance(all_roles.data, list) and all_roles.data


@allure.story("角色管理")
@allure.title("创建角色成功并落库")
@pytest.mark.case_id("MALL-ADM-RBAC-002")
def test_role_create(temp_role, db):
    row = db.query_one("select id, name, status from ums_role where id=%s", (temp_role["id"],))
    assert row["name"] == temp_role["name"]


@allure.story("角色管理")
@allure.title("修改角色名称后详情同步")
@pytest.mark.case_id("MALL-ADM-RBAC-003")
def test_role_update(admin_role_api, temp_role, db):
    new_name = temp_role["name"] + "_upd"
    A.assert_success(admin_role_api.update(temp_role["id"], {
        "id": temp_role["id"], "name": new_name, "description": "更新后", "status": 1, "sort": 1, "adminCount": 0,
    }))
    row = db.query_one("select name from ums_role where id=%s", (temp_role["id"],))
    assert row["name"] == new_name


@allure.story("角色资源")
@allure.title("分配菜单后角色菜单列表可查回")
@pytest.mark.case_id("MALL-ADM-RBAC-004")
def test_role_alloc_menu(admin_role_api, temp_role):
    menus = admin_role_api.c.get("/menu/list/0", params={"pageNum": 1, "pageSize": 10})
    A.assert_success(menus)
    menu_ids = [m["id"] for m in (menus.data.get("list") or [])][:2]
    if not menu_ids:
        pytest.skip("没有可分配的菜单")

    A.assert_success(admin_role_api.alloc_menu(temp_role["id"], menu_ids))
    allocated = admin_role_api.list_menu(temp_role["id"])
    A.assert_success(allocated)
    ids = [m["id"] for m in (allocated.data or [])]
    assert set(menu_ids).issubset(set(ids)), f"菜单分配未生效：期望 {menu_ids}，实际 {ids}"


@allure.story("角色资源")
@allure.title("分配资源后角色资源列表可查回")
@pytest.mark.case_id("MALL-ADM-RBAC-005")
def test_role_alloc_resource(admin_role_api, temp_role):
    resources = admin_role_api.c.get("/resource/listAll")
    A.assert_success(resources)
    res_ids = [r["id"] for r in (resources.data or [])][:2]
    if not res_ids:
        pytest.skip("没有可分配的资源")

    A.assert_success(admin_role_api.alloc_resource(temp_role["id"], res_ids))
    allocated = admin_role_api.list_resource(temp_role["id"])
    A.assert_success(allocated)
    ids = [r["id"] for r in (allocated.data or [])]
    assert set(res_ids).issubset(set(ids)), f"资源分配未生效：期望 {res_ids}，实际 {ids}"


@allure.story("角色管理")
@allure.title("启用/禁用角色状态")
@pytest.mark.case_id("MALL-ADM-RBAC-006")
def test_role_update_status(admin_role_api, temp_role, db):
    A.assert_success(admin_role_api.update_status(temp_role["id"], 0))
    assert int(db.query_one("select status from ums_role where id=%s", (temp_role["id"],))["status"]) == 0
    A.assert_success(admin_role_api.update_status(temp_role["id"], 1))
    assert int(db.query_one("select status from ums_role where id=%s", (temp_role["id"],))["status"]) == 1


@allure.story("权限校验")
@allure.title("未分配资源的新管理员访问业务接口应被拒绝")
@pytest.mark.security
@pytest.mark.case_id("MALL-ADM-RBAC-007")
def test_new_admin_has_no_permission(settings, admin_anon):
    """新建管理员默认无角色/资源，访问商品接口应 403（而不是 200）。"""
    acc = {"username": data_factory.unique_username("adm_"), "password": "Test@1234"}
    reg = admin_anon.post("/admin/register", json_body={**acc, "nickName": "自动化", "note": "rbac"})
    if reg.code != 200:
        pytest.skip(f"注册管理员失败：{reg.message}")

    login = admin_anon.post("/admin/login", json_body=acc)
    assert login.code == 200, f"新管理员登录失败：{login}"
    client = HttpClient(settings.admin.base_url, settings.admin.timeout, "new-admin").set_token(login.data["token"])

    resp = client.get("/product/list", params={"pageNum": 1, "pageSize": 5})
    assert resp.code == 403, f"无资源管理员访问商品接口未返回 403：{resp}"
    assert resp.code != 200


@allure.story("权限校验")
@allure.title("未登录访问角色接口被拦截")
@pytest.mark.case_id("MALL-ADM-RBAC-008")
def test_role_list_without_token(admin_anon):
    A.assert_code(admin_anon.get("/role/list", params={"pageNum": 1, "pageSize": 5}), 401)
