# -*- coding: utf-8 -*-
"""在 CI/容器环境抓取 Jenkins 流水线页面截图（通过远程 Selenium）。

用法（在 jenkins 容器内执行）:
  docker exec -e SELENIUM_REMOTE_URL=http://selenium:4444/wd/hub mall-jenkins \
    bash -lc "cd /var/jenkins_home/mall && python3 jenkins/screenshot_remote.py"
输出: docs/images/jenkins-pipeline.png、jenkins-build.png
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "images"
OUT.mkdir(parents=True, exist_ok=True)
REMOTE = os.environ.get("SELENIUM_REMOTE_URL", "http://selenium:4444/wd/hub")
JENKINS = os.environ.get("JENKINS_URL", "http://mall-jenkins:8080")
JOB = "mall-cicd"


def main():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1600,1200")
    opts.add_argument("--lang=zh-CN")

    driver = webdriver.Remote(command_executor=REMOTE, options=opts)
    driver.set_page_load_timeout(60)
    try:
        driver.get(f"{JENKINS}/login")
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.NAME, "j_username")))
        driver.find_element(By.NAME, "j_username").send_keys("admin")
        driver.find_element(By.NAME, "j_password").send_keys("admin123")
        driver.find_element(By.NAME, "Submit").click()
        time.sleep(4)

        driver.get(f"{JENKINS}/job/{JOB}/")
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.ID, "pipeline-box")))
        time.sleep(3)
        p1 = OUT / "jenkins-pipeline.png"
        driver.save_screenshot(str(p1))
        print(f"saved: {p1}")

        driver.get(f"{JENKINS}/job/{JOB}/lastBuild/")
        time.sleep(5)
        p2 = OUT / "jenkins-build.png"
        driver.save_screenshot(str(p2))
        print(f"saved: {p2}")
        print("title:", driver.title)
    finally:
        driver.quit()


if __name__ == "__main__":
    sys.exit(main())
