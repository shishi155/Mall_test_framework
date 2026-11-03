# -*- coding: utf-8 -*-
"""就地更新 Jenkins 任务配置（保留构建历史），失败则回退为删除重建。"""
from __future__ import annotations

import sys
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
from create_job import AUTH, JENKINS, JOB, crumb, job_xml, wait_ready  # noqa: E402


def main():
    wait_ready()
    script = (BASE / "Jenkinsfile").read_text(encoding="utf-8").lstrip("\ufeff")
    escaped = script.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    xml = job_xml(escaped).encode("utf-8")

    s = requests.Session()
    headers = {"Content-Type": "application/xml", **crumb(s)}
    r = s.post(f"{JENKINS}/job/{JOB}/config.xml", data=xml, headers=headers, auth=AUTH, timeout=30)
    print(f"更新配置: HTTP {r.status_code}")
    if r.status_code in (200, 204):
        print("已就地更新（构建历史保留）")
        return
    print(r.text[:800])
    print("回退：删除并重建任务")
    d = s.post(f"{JENKINS}/job/{JOB}/doDelete", headers=crumb(s), auth=AUTH, timeout=30)
    print(f"删除: HTTP {d.status_code}")
    c = s.post(f"{JENKINS}/createItem?name={JOB}", data=xml, headers={"Content-Type": "application/xml", **crumb(s)},
               auth=AUTH, timeout=30)
    print(f"重建: HTTP {c.status_code}")
    if c.status_code >= 400:
        raise SystemExit(c.text[:400])


if __name__ == "__main__":
    main()
