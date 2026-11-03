"""后台管理端 UI 冒烟（Selenium + Page Object）。

覆盖：登录、未登录拦截、首页框架、商品列表/搜索、订单列表、权限用户列表、
未知路由兜底、控制台错误检查。失败时自动截图 + DOM + 控制台日志（见 tests/ui/conftest.py）。
"""
from __future__ import annotations

import allure
import pytest
from selenium.webdriver.common.by import By

from ui.browser import console_errors
from ui.pages import LoginPage, OrderListPage, ProductListPage

pytestmark = [
    pytest.mark.ui,
    pytest.mark.ui_smoke,
    allure.epic("mall 商城"),
    allure.feature("后台-UI 冒烟"),
]


@allure.story("登录页")
@allure.title("登录页渲染完整：用户名/密码/登录按钮/体验账号")
@pytest.mark.case_id("MALL-UI-001")
def test_login_page_render(login_page):
    with allure.step("校验页面标题与路由"):
        assert "mall" in login_page.driver.title.lower(), f"标题异常：{login_page.driver.title}"
        assert login_page.route() == "#/login", f"未进入登录页：{login_page.route()}"

    with allure.step("校验输入框与按钮"):
        assert login_page.driver.find_element(*LoginPage.USER_INPUT).is_displayed()
        assert login_page.driver.find_element(*LoginPage.PWD_INPUT).is_displayed()
        assert login_page.driver.find_element(*LoginPage.LOGIN_BTN).is_displayed()
        body = login_page.body_text()
        assert "登录" in body, f"页面缺少登录按钮文案：{body[:80]}"


@allure.story("登录")
@allure.title("错误密码给出提示且停留在登录页")
@pytest.mark.case_id("MALL-UI-002")
def test_login_wrong_password(driver, login_page):
    login_page.login("admin", "Wrong@123456")
    msg = login_page.wait_error_message()

    with allure.step("校验错误提示与路由"):
        assert msg, "错误密码未出现任何提示"
        assert "密码" in msg or "错误" in msg, f"提示文案不可读：{msg}"
        assert login_page.route() == "#/login", f"登录失败却跳转了：{login_page.route()}"


@allure.story("登录")
@allure.title("正确账号密码登录成功进入首页，菜单完整")
@pytest.mark.case_id("MALL-UI-003")
def test_login_success(logged_in):
    with allure.step("校验路由与菜单"):
        assert logged_in.route() == "#/home", f"登录后未进入首页：{logged_in.route()}"
        menus = logged_in.menu_texts()
        assert menus, "侧边菜单为空"
        for expected in ("首页", "商品", "订单", "权限"):
            assert any(expected in m for m in menus), f"菜单缺少「{expected}」，实际：{menus[:12]}"


@allure.story("权限")
@allure.title("未登录直接访问商品页应被重定向到登录页")
@pytest.mark.case_id("MALL-UI-004")
def test_protected_route_redirect(driver, ui_settings):
    driver.get(f"{ui_settings.web.base_url}/#/pms/product")
    page = LoginPage(driver, ui_settings.web.base_url)
    page.wait_visible(*LoginPage.USER_INPUT, timeout=15)
    assert page.route() == "#/login", f"未登录访问受保护页面未被拦截：{page.route()}"


@allure.story("商品")
@allure.title("商品列表页加载并渲染数据表格")
@pytest.mark.case_id("MALL-UI-005")
def test_product_list(logged_in, driver, ui_settings):
    page = ProductListPage(driver, ui_settings.web.base_url)
    with allure.step("从菜单路由进入商品列表"):
        page.goto_hash("/pms/product", wait=4)
    with allure.step("校验表格与分页"):
        assert page.route() == "#/pms/product", f"路由异常：{page.route()}"
        rows = page.row_count()
        assert rows > 0, f"商品列表无数据行，body={page.body_text()[:200]}"
        assert "商品" in page.body_text()


@allure.story("商品")
@allure.title("商品列表关键字搜索生效")
@pytest.mark.case_id("MALL-UI-006")
def test_product_search(logged_in, driver, ui_settings):
    page = ProductListPage(driver, ui_settings.web.base_url)
    page.goto_hash("/pms/product", wait=4)
    before = page.row_count()
    assert before > 0, "商品列表为空，无法执行搜索"

    page.search("手机")
    after = page.wait_row_count_change(before)
    body = page.body_text()
    with allure.step("校验搜索结果"):
        assert after >= 1, f"搜索「手机」无结果，行数 {before} -> {after}"
        assert "手机" in body, "搜索结果未包含关键字"


@allure.story("订单")
@allure.title("订单列表页加载并展示订单数据与状态筛选")
@pytest.mark.case_id("MALL-UI-007")
def test_order_list(logged_in, driver, ui_settings):
    page = OrderListPage(driver, ui_settings.web.base_url)
    page.goto_hash("/oms/order", wait=5)
    body = page.body_text()

    with allure.step("校验路由与表格数据"):
        assert page.route() == "#/oms/order", f"路由异常：{page.route()}"
        rows = page.row_count()
        assert rows > 0, f"订单列表无数据行，body={body[:200]}"

    with allure.step("校验状态筛选项存在"):
        assert "订单状态" in body, "缺少订单状态筛选"
        assert any(k in body for k in ("未支付", "待发货", "已发货", "已关闭")), "订单状态文案异常"


@allure.story("权限")
@allure.title("用户列表页加载并展示后台账号")
@pytest.mark.case_id("MALL-UI-008")
def test_user_list(logged_in, driver, ui_settings):
    page = LoginPage(driver, ui_settings.web.base_url)
    page.goto_hash("/ums/admin", wait=5)

    rows = driver.find_elements(By.CSS_SELECTOR, ".el-table__row")
    body = page.body_text()
    with allure.step("校验用户列表数据"):
        assert rows, f"用户列表无数据行，body={body[:200]}"
        assert "admin" in body, "用户列表中未出现 admin 账号"


@allure.story("路由兜底")
@allure.title("访问不存在的路由应有 404 页面而不是白屏")
@pytest.mark.xfail(reason="已知缺陷 U-01：访问未定义路由（如 /pms/product/index）整页白屏，无 404 兜底", strict=False)
@pytest.mark.case_id("MALL-UI-009")
def test_unknown_route_fallback(logged_in, driver, ui_settings):
    page = LoginPage(driver, ui_settings.web.base_url)
    page.goto_hash("/pms/product/index", wait=4)
    body = page.body_text().strip()
    assert body, "未知路由页面为空白（白屏）"
    assert "404" in body or "不存在" in body, f"未知路由未给出 404 提示，实际内容：{body[:120]}"


@allure.story("稳定性")
@allure.title("登录、首页、商品列表无 JS 严重错误")
@pytest.mark.case_id("MALL-UI-010")
def test_no_console_severe(logged_in, driver, ui_settings):
    ProductListPage(driver, ui_settings.web.base_url).goto_hash("/pms/product", wait=4)
    errors = console_errors(driver)
    assert not errors, "控制台存在 JS 严重错误：" + "; ".join(e["message"][:150] for e in errors[:3])


@allure.story("稳定性")
@allure.title("用户列表页无 JS 严重错误（角色筛选依赖）")
@pytest.mark.case_id("MALL-UI-011")
def test_user_list_no_console_severe(logged_in, driver, ui_settings):
    LoginPage(driver, ui_settings.web.base_url).goto_hash("/ums/admin", wait=5)
    errors = console_errors(driver)
    assert not errors, "控制台存在 JS 严重错误：" + "; ".join(e["message"][:150] for e in errors[:3])
