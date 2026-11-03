"""Selenium 浏览器封装：驱动创建 + 失败证据采集（截图 / DOM / 控制台日志）。"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

import allure
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

try:
    from config.settings import Settings
except Exception:  # pragma: no cover
    Settings = None  # type: ignore

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "build"
CHROME_CANDIDATES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
]
DRIVER_CANDIDATES = [
    WORK / "drivers" / "chromedriver-win64" / "chromedriver.exe",
    Path(os.environ["CHROMEDRIVER_PATH"]) if os.environ.get("CHROMEDRIVER_PATH") else None,
]
EVIDENCE_DIR = ROOT / "reports" / "ui-evidence"


def _first_existing(paths):
    for p in paths:
        if p and Path(p).exists():
            return Path(p)
    return None


def create_driver(headless: bool = True, window: str = "1440,900", keep_profile: bool = False):
    """创建 Chrome 驱动。

    两种模式（按环境变量自动选择）：
    - 本地模式：显式指定 chromedriver（Selenium Manager 下载的版本与 Chrome 156 不匹配），
      且必须把 TEMP/TMP 指到工作区，否则 Chrome 报 “cannot create temp dir for unpacking extensions”；
    - 远程模式（CI）：设置 SELENIUM_REMOTE_URL（如 http://selenium:4444/wd/hub），
      直接连 selenium/standalone-chrome 容器，不再关心本机 Chrome 与驱动版本。

    每次使用独立 profile，否则上一个用例登录后的 token 会让 /#/login 直接跳首页。
    """
    remote_url = os.environ.get("SELENIUM_REMOTE_URL", "").strip()

    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    opts.add_argument(f"--window-size={window}")
    opts.add_argument("--lang=zh-CN")
    opts.set_capability("goog:loggingPrefs", {"browser": "ALL"})

    if remote_url:
        driver = webdriver.Remote(command_executor=remote_url, options=opts)
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(0)
        return driver

    tmpdir = WORK / "tmp"
    tmpdir.mkdir(parents=True, exist_ok=True)
    os.environ["TEMP"] = str(tmpdir)
    os.environ["TMP"] = str(tmpdir)
    tempfile.tempdir = str(tmpdir)
    profile = Path(tempfile.mkdtemp(prefix="chrome-profile-", dir=str(tmpdir)))
    opts.add_argument(f"--user-data-dir={profile}")

    chrome = _first_existing(CHROME_CANDIDATES)
    if chrome:
        opts.binary_location = str(chrome)

    driver_path = _first_existing(DRIVER_CANDIDATES)
    service = Service(executable_path=str(driver_path)) if driver_path else Service()
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(30)
    driver.implicitly_wait(0)
    return driver


# ---------------- 失败证据采集 ----------------
def _case_dir(case_name: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    d = EVIDENCE_DIR / f"{case_name}_{stamp}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def capture_evidence(driver, case_name: str) -> dict:
    """截图 + DOM + 控制台日志，同时落盘并 attach 到 Allure。返回各文件路径。"""
    d = _case_dir(case_name)
    result = {"dir": str(d)}

    # 1) 截图
    try:
        png = d / "screenshot.png"
        driver.save_screenshot(str(png))
        result["screenshot"] = str(png)
        allure.attach.file(str(png), name="失败截图", attachment_type=allure.attachment_type.PNG)
    except Exception as e:  # pragma: no cover
        result["screenshot_error"] = str(e)

    # 2) DOM
    try:
        html = d / "page.html"
        html.write_text(driver.page_source, encoding="utf-8")
        result["dom"] = str(html)
        allure.attach(
            f"URL: {driver.current_url}\n标题: {driver.title}\n\n{driver.page_source[:20000]}",
            name="失败时 DOM 快照",
            attachment_type=allure.attachment_type.HTML,
        )
    except Exception as e:  # pragma: no cover
        result["dom_error"] = str(e)

    # 3) 浏览器控制台日志
    try:
        logs = driver.get_log("browser")
        log_path = d / "console.log"
        log_path.write_text(
            "\n".join(f"[{l['level']}] {l['timestamp']} {l['message']}" for l in logs),
            encoding="utf-8",
        )
        result["console"] = str(log_path)
        allure.attach(
            json.dumps(logs, ensure_ascii=False, indent=2),
            name="浏览器控制台日志",
            attachment_type=allure.attachment_type.JSON,
        )
    except Exception as e:  # pragma: no cover
        result["console_error"] = str(e)

    # 4) 环境信息
    try:
        info = {"url": driver.current_url, "title": driver.title, "window": driver.get_window_size()}
        (d / "context.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
        result["context"] = str(d / "context.json")
    except Exception:  # pragma: no cover
        pass

    return result


def console_errors(driver) -> list:
    """返回浏览器控制台中的 SEVERE 级日志（用于 UI 缺陷判定）。"""
    try:
        return [l for l in driver.get_log("browser") if l.get("level") == "SEVERE"]
    except Exception:  # pragma: no cover
        return []
