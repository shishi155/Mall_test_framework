"""后台管理端页面对象（Page Object）。

定位策略：
- 输入框优先用 placeholder（Element Plus 的 el-input 内部真实 input）；
- 按钮用按钮文字（ElButton 内部 span）；
- 表格行用 .el-table__body tr，菜单用 .el-menu-item。
"""
from __future__ import annotations

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

DEFAULT_TIMEOUT = 15

# 直接写值并触发 input 事件：Element Plus 登录页会把用户名预填成 admin，
# 用 send_keys 会变成 "adminadmin"，因此统一走 JS 赋值。
SET_VALUE_JS = """
const el = arguments[0], val = arguments[1];
el.value = val;
el.dispatchEvent(new Event('input', {bubbles: true}));
el.dispatchEvent(new Event('change', {bubbles: true}));
"""


class BasePage:
    def __init__(self, driver, base_url: str):
        self.driver = driver
        self.base_url = base_url.rstrip("/")

    def set_value(self, by, value, text: str):
        el = self.wait_visible(by, value)
        self.driver.execute_script(SET_VALUE_JS, el, text)
        return el

    def goto_hash(self, path: str, wait: float = 3.0):
        """hash 路由切换（不整页刷新），等待渲染。"""
        import time
        self.driver.execute_script(f"window.location.hash = '{path}'")
        time.sleep(wait)
        return self

    def open(self, path: str = "/"):
        self.driver.get(f"{self.base_url}{path}")
        return self

    def wait(self, timeout: int = DEFAULT_TIMEOUT) -> WebDriverWait:
        return WebDriverWait(self.driver, timeout)

    def wait_visible(self, by, value, timeout: int = DEFAULT_TIMEOUT):
        return self.wait(timeout).until(EC.visibility_of_element_located((by, value)))

    def wait_present(self, by, value, timeout: int = DEFAULT_TIMEOUT):
        return self.wait(timeout).until(EC.presence_of_element_located((by, value)))

    def route(self) -> str:
        """hash 路由，如 #/login。"""
        url = self.driver.current_url
        return "#" + url.split("#", 1)[1] if "#" in url else ""

    def body_text(self) -> str:
        return self.driver.find_element(By.TAG_NAME, "body").text

    def take_screenshot(self, path: str):
        return self.driver.save_screenshot(path)


class LoginPage(BasePage):
    USER_INPUT = (By.XPATH, "//input[@placeholder='请输入用户名']")
    PWD_INPUT = (By.XPATH, "//input[@placeholder='请输入密码']")
    LOGIN_BTN = (By.XPATH, "//button[contains(normalize-space(.), '登录')]")
    ERROR_MSG = (By.CSS_SELECTOR, ".el-message--error")

    def open_login(self) -> "LoginPage":
        self.open("/#/login")
        self.wait_visible(*self.USER_INPUT)
        return self

    def is_loaded(self) -> bool:
        try:
            self.wait_visible(*self.USER_INPUT, timeout=5)
            self.wait_visible(*self.PWD_INPUT, timeout=5)
            return self.driver.find_element(*self.LOGIN_BTN).is_displayed()
        except TimeoutException:
            return False

    def login(self, username: str, password: str) -> "LoginPage":
        self.set_value(*self.USER_INPUT, username)
        self.set_value(*self.PWD_INPUT, password)
        self.driver.find_element(*self.LOGIN_BTN).click()
        return self

    def wait_error_message(self, timeout: int = 10) -> str:
        try:
            el = self.wait(timeout).until(EC.visibility_of_element_located(self.ERROR_MSG))
            return el.text
        except TimeoutException:
            return ""


class LayoutPage(BasePage):
    """登录后的整体框架：侧边菜单 + 顶部导航。"""

    MENU_ITEMS = (By.CSS_SELECTOR, ".el-menu-item, .el-sub-menu__title")
    SIDEBAR = (By.CSS_SELECTOR, ".el-menu, .sidebar-container")

    def wait_ready(self, timeout: int = 15) -> "LayoutPage":
        self.wait(timeout).until(EC.presence_of_element_located(self.MENU_ITEMS))
        return self

    def menu_texts(self) -> list:
        return [e.text.strip() for e in self.driver.find_elements(*self.MENU_ITEMS) if e.text.strip()]

    def goto(self, path: str) -> "LayoutPage":
        self.open(f"/{path}")
        return self

    def logout(self) -> "LayoutPage":
        """展开右上角用户菜单并点击退出登录。"""
        from selenium.webdriver.common.action_chains import ActionChains
        trigger = self.driver.find_elements(By.CSS_SELECTOR, ".el-dropdown, .avatar-container, .user-info")
        if trigger:
            ActionChains(self.driver).move_to_element(trigger[0]).perform()
            self.driver.find_element(By.CSS_SELECTOR, ".el-dropdown-menu").click()
        return self


class ProductListPage(BasePage):
    PATH = "/#/pms/product"
    TABLE_ROWS = (By.CSS_SELECTOR, ".el-table__body tr")
    SEARCH_INPUT = (By.CSS_SELECTOR, "input[placeholder='商品名称']")
    SEARCH_BTN = (By.XPATH, "//button[contains(normalize-space(.), '查询结果')]")

    def open_list(self) -> "ProductListPage":
        self.open(self.PATH)
        self.wait_visible(*self.TABLE_ROWS, timeout=20)
        return self

    def rows(self) -> list:
        return self.driver.find_elements(*self.TABLE_ROWS)

    def row_count(self) -> int:
        return len(self.rows())

    def search(self, keyword: str) -> "ProductListPage":
        box = self.wait_visible(*self.SEARCH_INPUT)
        box.clear()
        box.send_keys(keyword)
        self.driver.find_element(*self.SEARCH_BTN).click()
        return self

    def wait_row_count_change(self, old: int, timeout: int = 15) -> int:
        self.wait(timeout).until(lambda d: len(d.find_elements(*self.TABLE_ROWS)) != old)
        return self.row_count()


class OrderListPage(BasePage):
    PATH = "/#/oms/order"
    TABLE_ROWS = (By.CSS_SELECTOR, ".el-table__body tr")
    TAB_ITEMS = (By.CSS_SELECTOR, ".el-tabs__item")

    def open_list(self) -> "OrderListPage":
        self.open(self.PATH)
        self.wait_visible(*self.TABLE_ROWS, timeout=20)
        return self

    def row_count(self) -> int:
        return len(self.driver.find_elements(*self.TABLE_ROWS))

    def tabs(self) -> list:
        return [e.text.strip() for e in self.driver.find_elements(*self.TAB_ITEMS) if e.text.strip()]
