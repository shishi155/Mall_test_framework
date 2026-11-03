# -*- coding: utf-8 -*-
"""创建/更新 Jenkins 流水线任务，并可触发一次构建。

用法:
  python jenkins/create_job.py            # 建任务并触发构建，跟随日志直到结束
  python jenkins/create_job.py --no-build # 只建任务
  python jenkins/create_job.py --watch    # 只跟随最近一次构建
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
JENKINS = "http://localhost:8081"
AUTH = ("admin", "admin123")
JOB = "mall-cicd"


def wait_ready(timeout: int = 240):
    print(f"等待 Jenkins 就绪 ({JENKINS}) ...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"{JENKINS}/api/json", auth=AUTH, timeout=5)
            if r.status_code == 200:
                print("Jenkins 已就绪")
                return True
            if r.status_code == 403:
                # 还没初始化完 / JCasC 未生效
                pass
        except requests.RequestException:
            pass
        time.sleep(5)
    raise SystemExit("Jenkins 启动超时，检查容器日志：docker logs mall-jenkins")


def crumb(session: requests.Session):
    r = session.get(f"{JENKINS}/crumbIssuer/api/json", auth=AUTH, timeout=10)
    if r.status_code == 200:
        data = r.json()
        return {data["crumbRequestField"]: data["crumb"]}
    return {}


def job_xml(script: str) -> str:
    return f"""<?xml version='1.1' encoding='UTF-8'?>
<flow-definition plugin="workflow-job">
  <description>mall 商城测试流水线：环境检查 → 接口冒烟 → 接口全量 → UI 冒烟 → 性能基线（可选）</description>
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
        <hudson.model.BooleanParameterDefinition>
          <name>RUN_UI</name>
          <defaultValue>true</defaultValue>
          <description>是否执行 Selenium UI 冒烟</description>
        </hudson.model.BooleanParameterDefinition>
        <hudson.model.BooleanParameterDefinition>
          <name>RUN_PERF</name>
          <defaultValue>false</defaultValue>
          <description>是否执行性能基线（约 4 分钟）</description>
        </hudson.model.BooleanParameterDefinition>
      </parameterDefinitions>
    </hudson.model.ParametersDefinitionProperty>
  </properties>
  <definition class="org.jenkinsci.plugins.workflow.cps.CpsFlowDefinition" plugin="workflow-cps">
    <script>{script}</script>
    <sandbox>true</sandbox>
  </definition>
  <triggers/>
  <disabled>false</disabled>
</flow-definition>"""


def upsert_job():
    script = (BASE / "Jenkinsfile").read_text(encoding="utf-8").lstrip("\ufeff")
    # XML 转义
    escaped = (script.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    s = requests.Session()
    headers = {"Content-Type": "application/xml", **crumb(s)}

    exists = s.get(f"{JENKINS}/job/{JOB}/api/json", auth=AUTH, timeout=10).status_code == 200
    if exists:
        # 配置更新在部分版本上会 500，直接删掉重建更稳
        d = s.post(f"{JENKINS}/job/{JOB}/doDelete", headers=headers, auth=AUTH, timeout=30)
        print(f"删除旧任务 {JOB}: HTTP {d.status_code}")

    r = s.post(f"{JENKINS}/createItem?name={JOB}", data=job_xml(escaped).encode("utf-8"),
               headers=headers, auth=AUTH, timeout=30)
    print(f"创建任务 {JOB}: HTTP {r.status_code}")
    if r.status_code >= 400:
        raise SystemExit(f"任务创建失败：{r.status_code} {r.text[:600]}")


def trigger():
    s = requests.Session()
    headers = crumb(s)
    # 参数化任务必须用 buildWithParameters；非参数化任务用 build
    r = s.post(f"{JENKINS}/job/{JOB}/buildWithParameters",
               params={"SCOPE": "smoke", "RUN_UI": "true", "RUN_PERF": "false"},
               headers=headers, auth=AUTH, timeout=30)
    if r.status_code >= 400:
        r = s.post(f"{JENKINS}/job/{JOB}/build", headers=headers, auth=AUTH, timeout=30)
    print(f"触发构建: HTTP {r.status_code}")
    if r.status_code >= 400:
        raise SystemExit(f"触发失败：{r.status_code} {r.text[:300]}")


def watch(timeout: int = 1800):
    s = requests.Session()
    # 等待构建开始
    number = None
    for _ in range(60):
        info = s.get(f"{JENKINS}/job/{JOB}/lastBuild/api/json", auth=AUTH, timeout=10)
        if info.status_code == 200 and info.json().get("number"):
            number = info.json()["number"]
            break
        time.sleep(3)
    if not number:
        raise SystemExit("没有找到构建记录")

    print(f"跟随构建 #{number} ...")
    last_len = 0
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = s.get(f"{JENKINS}/job/{JOB}/{number}/consoleText", auth=AUTH, timeout=15)
        text = r.text
        if len(text) > last_len:
            sys.stdout.write(text[last_len:].replace("\ufeff", ""))
            sys.stdout.flush()
            last_len = len(text)

        j = s.get(f"{JENKINS}/job/{JOB}/{number}/api/json", auth=AUTH, timeout=10)
        if j.status_code == 200:
            data = j.json()
            if data.get("result"):
                print(f"\n\n构建 #{number} 结果: {data['result']} | 耗时 {data.get('duration', 0) / 1000:.1f}s")
                return data["result"]
        time.sleep(5)
    raise SystemExit("等待构建结束超时")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--watch", action="store_true")
    args = ap.parse_args()

    wait_ready()
    if not args.watch:
        upsert_job()
        if args.no_build:
            return
        trigger()
    watch()


if __name__ == "__main__":
    main()
