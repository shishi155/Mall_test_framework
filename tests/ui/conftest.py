"""UI 测试全局夹具与失败证据采集。"""
from __future__ import annotations

import json
import os
import shutil

import allure
import pytest

from config.settings import load_settings
from ui.browser import EVIDENCE_DIR, capture_evidence, create_driver
from ui.pages import LayoutPage, LoginPage

SET_VALUE_JS = """
const el = arguments[0], val = arguments[1];
el.value = val;
el.dispatchEvent(new Event('input', {bubbles: true}));
el.dispatchEvent(new Event('change', {bubbles: true}));
"""


def pytest_configure(config):
    config.addinivalue_line("markers", "ui: Selenium UI 用例")
    config.addinivalue_line("markers", "ui_smoke: UI 冒烟用例")


@pytest.fixture(scope="session")
def ui_settings():
    return load_settings()


@pytest.fixture()
def driver(ui_settings):
    headless = os.environ.get("UI_HEADLESS", "1") != "0"
    d = create_driver(headless=headless)
    yield d
    try:
        d.quit()
    finally:
        # 清理本次 profile，避免占用磁盘
        for opt in d.capabilities.get("goog:chromeOptions", {}).get("args", []):
            if opt.startswith("--user-data-dir="):
                shutil.rmtree(opt.split("=", 1)[1], ignore_errors=True)


@pytest.fixture()
def login_page(driver, ui_settings) -> LoginPage:
    return LoginPage(driver, ui_settings.web.base_url).open_login()


@pytest.fixture()
def logged_in(driver, ui_settings) -> LayoutPage:
    """登录并等待框架渲染完成。"""
    page = LoginPage(driver, ui_settings.web.base_url).open_login()
    acc = ui_settings.admin_account
    page.set_value(*LoginPage.USER_INPUT, acc["username"])
    page.set_value(*LoginPage.PWD_INPUT, acc["password"])
    driver.find_element(*LoginPage.LOGIN_BTN).click()

    layout = LayoutPage(driver, ui_settings.web.base_url)
    layout.wait_ready()
    return layout


def _driver_from_item(item):
    """尽力拿到用例的 driver（setup/call 阶段都可能失败）。"""
    for name in ("driver", "logged_in", "login_page"):
        obj = item.funcargs.get(name)
        if obj is None:
            continue
        return getattr(obj, "driver", obj)
    return None


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if not report.failed:
        return
    drv = _driver_from_item(item)
    if drv is None:
        return
    try:
        evidence = capture_evidence(drv, item.name)
        report.sections.append(("UI 证据", json.dumps(evidence, ensure_ascii=False, indent=2)))
    except Exception as e:  # pragma: no cover
        report.sections.append(("UI 证据采集失败", str(e)))
