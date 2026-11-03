# -*- coding: utf-8 -*-
"""验证 Jenkins 定时触发器真的会到点构建：临时建一个每 2 分钟跑的任务，观察后删除。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
from create_job import AUTH, JENKINS, crumb, wait_ready  # noqa: E402
from create_jobs import job_xml  # noqa: E402

JOB = "mall-cron-selftest"


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    wait_ready()
    script = (BASE / "Jenkinsfile").read_text(encoding="utf-8").lstrip("\ufeff")
    escaped = script.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    defaults = {"SCOPE": "smoke", "RUN_UI": "false", "RUN_PERF": "false",
                "NOTIFY_DAILY": "false", "NOTIFY_SELFTEST": "false"}
    xml = job_xml(escaped, "定时触发器自检（每 2 分钟）", defaults, "*/2 * * * *")

    s = requests.Session()
    h = {"Content-Type": "application/xml", **crumb(s)}
    if s.get(f"{JENKINS}/job/{JOB}/api/json", auth=AUTH, timeout=10).status_code == 200:
        s.post(f"{JENKINS}/job/{JOB}/doDelete", headers=h, auth=AUTH, timeout=30)
    r = s.post(f"{JENKINS}/createItem?name={JOB}", data=xml.encode("utf-8"), headers=h, auth=AUTH, timeout=30)
    print(f"创建 {JOB}（*/2 * * * *）: HTTP {r.status_code}")

    print("等待定时构建触发（最多 4 分钟）...")
    build = None
    for _ in range(48):
        time.sleep(5)
        info = s.get(f"{JENKINS}/job/{JOB}/api/json?tree=builds[number,actions[causes[shortDescription]]]",
                     auth=AUTH, timeout=10)
        if info.status_code == 200 and info.json().get("builds"):
            builds = info.json()["builds"]
            desc = ""
            for act in builds[0].get("actions", []):
                for cause in act.get("causes", []):
                    desc += cause.get("shortDescription", "")
            build = {"number": builds[0]["number"], "cause": desc}
            break

    if build:
        print(f"✅ 定时触发成功: #{build['number']} 原因={build['cause']!r}")
    else:
        print("❌ 4 分钟内未触发定时构建")

    # 删除测试任务
    s.post(f"{JENKINS}/job/{JOB}/doDelete", headers=crumb(s), auth=AUTH, timeout=30)
    print(f"已删除测试任务 {JOB}")
    return 0 if build else 1


if __name__ == "__main__":
    sys.exit(main())
