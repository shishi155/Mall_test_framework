# -*- coding: utf-8 -*-
"""创建/更新三条流水线任务（手动 / 工作日全量 / 每日含性能），并注册定时触发器。

用法:
  python jenkins/create_jobs.py              # 全部创建/更新
  python jenkins/create_jobs.py --only mall-cicd-daily
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
from create_job import AUTH, JENKINS, crumb, wait_ready  # noqa: E402

# 三个任务：默认参数 + cron（cron 为空表示只手动触发）
JOBS = {
    # 日常手动：冒烟 + UI，快
    "mall-cicd": {
        "desc": "mall 测试 · 手动触发（默认：冒烟 + UI）",
        "cron": "",
        "defaults": {"SCOPE": "smoke", "RUN_UI": "true", "RUN_PERF": "false",
                     "NOTIFY_DAILY": "false", "NOTIFY_SELFTEST": "false"},
    },
    # 工作日早上：全量接口 + UI，成功也发一封（每日汇总）
    "mall-cicd-daily": {
        "desc": "mall 测试 · 工作日 09:00 全量接口 + UI（成功也发汇总邮件）",
        "cron": "H 9 * * 1-5",
        "defaults": {"SCOPE": "full", "RUN_UI": "true", "RUN_PERF": "false",
                     "NOTIFY_DAILY": "true", "NOTIFY_SELFTEST": "false"},
    },
    # 每日凌晨：全量 + UI + 性能基线
    "mall-cicd-nightly": {
        "desc": "mall 测试 · 每日 02:00 全量接口 + UI + 性能基线",
        "cron": "H 2 * * *",
        "defaults": {"SCOPE": "full", "RUN_UI": "true", "RUN_PERF": "true",
                     "NOTIFY_DAILY": "false", "NOTIFY_SELFTEST": "false"},
    },
}


def job_xml(script: str, desc: str, defaults: dict, cron: str) -> str:
    def bool_param(name, value, text):
        return (f"""        <hudson.model.BooleanParameterDefinition>
          <name>{name}</name>
          <defaultValue>{value}</defaultValue>
          <description>{text}</description>
        </hudson.model.BooleanParameterDefinition>""")

    trigger = ""
    if cron:
        trigger = (f"""  <triggers>
    <hudson.triggers.TimerTrigger>
      <spec>{cron}</spec>
    </hudson.triggers.TimerTrigger>
  </triggers>""")

    return f"""<?xml version='1.1' encoding='UTF-8'?>
<flow-definition plugin="workflow-job">
  <description>{desc}</description>
  <keepDependencies>false</keepDependencies>
  <properties>
    <hudson.model.ParametersDefinitionProperty>
      <parameterDefinitions>
        <hudson.model.ChoiceParameterDefinition>
          <name>SCOPE</name>
          <description>接口执行范围：smoke=冒烟，full=全量</description>
          <choices>
            <string>smoke</string>
            <string>full</string>
          </choices>
        </hudson.model.ChoiceParameterDefinition>
{bool_param('RUN_UI', defaults['RUN_UI'], '是否执行 Selenium UI 冒烟')}
{bool_param('RUN_PERF', defaults['RUN_PERF'], '是否执行性能基线（约 4 分钟）')}
{bool_param('NOTIFY_DAILY', defaults['NOTIFY_DAILY'], '成功也发送邮件（每日汇总用）')}
{bool_param('NOTIFY_SELFTEST', defaults['NOTIFY_SELFTEST'], '额外发送一封通知自检邮件（验证 SMTP）')}
      </parameterDefinitions>
    </hudson.model.ParametersDefinitionProperty>
  </properties>
  <definition class="org.jenkinsci.plugins.workflow.cps.CpsFlowDefinition" plugin="workflow-cps">
    <script>{script}</script>
    <sandbox>true</sandbox>
  </definition>
{trigger}
  <disabled>false</disabled>
</flow-definition>"""


def upsert(session: requests.Session, name: str, xml: str):
    headers = {"Content-Type": "application/xml", **crumb(session)}
    exists = session.get(f"{JENKINS}/job/{name}/api/json", auth=AUTH, timeout=10).status_code == 200
    if exists:
        session.post(f"{JENKINS}/job/{name}/doDelete", headers=headers, auth=AUTH, timeout=30)
    r = session.post(f"{JENKINS}/createItem?name={name}", data=xml.encode("utf-8"),
                     headers=headers, auth=AUTH, timeout=30)
    print(f"{'重建' if exists else '创建'} {name}: HTTP {r.status_code}")
    if r.status_code >= 400:
        raise SystemExit(r.text[:400])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    args = ap.parse_args()

    wait_ready()
    script = (BASE / "Jenkinsfile").read_text(encoding="utf-8").lstrip("\ufeff")
    escaped = script.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    s = requests.Session()
    for name, cfg in JOBS.items():
        if args.only and name != args.only:
            continue
        upsert(s, name, job_xml(escaped, cfg["desc"], cfg["defaults"], cfg["cron"]))
        print(f"  cron={cfg['cron'] or '（仅手动）'} defaults={cfg['defaults']}")

    # 回读触发器确认
    for name in JOBS:
        if args.only and name != args.only:
            continue
        info = s.get(f"{JENKINS}/job/{name}/api/json?tree=triggers[spec]", auth=AUTH, timeout=10).json()
        specs = [t.get("spec") for t in info.get("triggers", []) if t.get("spec")]
        print(f"{name} 已注册触发器: {specs or '无'}")


if __name__ == "__main__":
    main()
