# -*- coding: utf-8 -*-
"""抓取 Jenkins 流水线页面截图（用于文档配图）。

用法: python jenkins/screenshot.py
输出: docs/images/jenkins-pipeline.png、jenkins-build.png
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "images"
OUT.mkdir(parents=True, exist_ok=True)

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DRIVER = ROOT / "build" / "drivers" / "chromedriver-win64" / "chromedriver.exe"
TMP = ROOT / "build" / "tmp"

JENKINS = "http://localhost:8081"
JOB_URL = f"{JENKINS}/job/mall-cicd/"


def main():
    TMP.mkdir(parents=True, exist_ok=True)
    os.environ["TEMP"] = str(TMP)
    os.environ["TMP"] = str(TMP)
    tempfile.tempdir = str(TMP)
    profile = TMP / "profile-screenshot"
    profile.mkdir(exist_ok=True)
    opts = Options()
    opts.binary_location = CHROME
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1600,1200")
    opts.add_argument("--lang=zh-CN")
    opts.add_argument(f"--user-data-dir={profile}")

    driver = webdriver.Chrome(service=Service(executable_path=str(DRIVER)), options=opts)
    driver.set_page_load_timeout(60)
    try:
        # 登录
        driver.get(f"{JENKINS}/login")
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.NAME, "j_username")))
        driver.find_element(By.NAME, "j_username").send_keys("admin")
        driver.find_element(By.NAME, "j_password").send_keys("admin123")
        driver.find_element(By.NAME, "Submit").click()
        time.sleep(4)

        # 任务页
        driver.get(JOB_URL)
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.ID, "pipeline-box")))
        time.sleep(3)
        driver.save_screenshot(str(OUT / "jenkins-pipeline.png"))
        print(f"saved: {OUT / 'jenkins-pipeline.png'}")

        # 最近一次构建页（含阶段视图）
        driver.get(f"{JOB_URL}lastBuild/")
        time.sleep(4)
        driver.save_screenshot(str(OUT / "jenkins-build.png"))
        print(f"saved: {OUT / 'jenkins-build.png'}")

        print("title:", driver.title)
    finally:
        driver.quit()


if __name__ == "__main__":
    sys.exit(main())
