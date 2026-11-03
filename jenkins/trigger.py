# -*- coding: utf-8 -*-
"""触发一次带参数的构建并跟随日志。

用法:
  python jenkins/trigger.py --scope full --ui true --perf true
  python jenkins/trigger.py --scope smoke
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from create_job import AUTH, JENKINS, JOB, crumb, watch, wait_ready  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", default="smoke", choices=["smoke", "full"])
    ap.add_argument("--ui", default="true")
    ap.add_argument("--perf", default="false")
    ap.add_argument("--no-watch", action="store_true")
    args = ap.parse_args()

    wait_ready()
    s = requests.Session()
    headers = crumb(s)
    params = {"SCOPE": args.scope, "RUN_UI": args.ui, "RUN_PERF": args.perf}
    r = s.post(f"{JENKINS}/job/{JOB}/buildWithParameters", params=params,
               headers=headers, auth=AUTH, timeout=30)
    print(f"触发构建 {params}: HTTP {r.status_code}")
    if r.status_code >= 400:
        print(r.text[:200])
        print("回退为无参构建（首次构建前任务尚未参数化）")
        r = s.post(f"{JENKINS}/job/{JOB}/build", headers=crumb(s), auth=AUTH, timeout=30)
        print(f"触发构建: HTTP {r.status_code}")
        if r.status_code >= 400:
            raise SystemExit(r.text[:400])

    if not args.no_watch:
        watch()


if __name__ == "__main__":
    main()
