# -*- coding: utf-8 -*-
"""构建通知：把 CI 结果通过邮件发出（QQ/163/企业邮箱均可）。

配置优先级：环境变量 > jenkins/notify.yaml > 未配置（只落日志不发送）

环境变量：
  SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASS
  SMTP_SECURITY      ssl（465）| starttls（587）| none（25）
  MAIL_FROM / MAIL_TO（多个用逗号分隔）
  NOTIFY_MODE        auto | fail-only | daily   （默认 auto：失败必发，成功仅在 daily 模式发）
  JOB_NAME / BUILD_NUMBER / BUILD_URL / BUILD_STATUS / BUILD_DURATION

用法：
  python jenkins/notify.py --status FAILURE --build 12 --duration 158
  python jenkins/notify.py --dry-run          # 只打印邮件内容，不发送（本地验证用）
"""
from __future__ import annotations

import argparse
import json
import os
import smtplib
import ssl
import sys
from datetime import datetime
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = Path(__file__).resolve().parent / "notify.yaml"
LOG_FILE = ROOT / "reports" / "notify.log"

DEFAULTS = {
    "smtp_host": "",
    "smtp_port": 465,
    "smtp_security": "ssl",
    "smtp_user": "",
    "smtp_pass": "",
    "mail_from": "",
    "mail_to": "",
    "notify_mode": "auto",
}


def load_config() -> dict:
    cfg = dict(DEFAULTS)

    # 1) yaml（极简解析，避免额外依赖）
    if CONFIG_FILE.exists():
        for line in CONFIG_FILE.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            k, v = line.split(":", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k in cfg and v:
                cfg[k] = int(v) if k == "smtp_port" else v

    # 2) 环境变量覆盖
    env_map = {
        "SMTP_HOST": "smtp_host", "SMTP_PORT": "smtp_port", "SMTP_SECURITY": "smtp_security",
        "SMTP_USER": "smtp_user", "SMTP_PASS": "smtp_pass",
        "MAIL_FROM": "mail_from", "MAIL_TO": "mail_to", "NOTIFY_MODE": "notify_mode",
    }
    for env, key in env_map.items():
        v = os.environ.get(env)
        if v:
            cfg[key] = int(v) if key == "smtp_port" else v
    return cfg


def fmt_duration(seconds: float) -> str:
    seconds = int(seconds or 0)
    if seconds >= 60:
        return f"{seconds // 60}分{seconds % 60}秒"
    return f"{seconds}秒"


def summarize_results() -> dict:
    """从 reports/junit 汇总用例数（有则填，没有就不展示）。"""
    out = {"total": 0, "failures": 0, "skipped": 0}
    junit_dir = ROOT / "reports" / "junit"
    if not junit_dir.exists():
        return out
    import xml.etree.ElementTree as ET
    for f in junit_dir.glob("*.xml"):
        try:
            root = ET.parse(f).getroot()
            suites = [root] if root.tag == "testsuite" else list(root)
            for s in suites:
                out["total"] += int(s.get("tests", 0))
                out["failures"] += int(s.get("failures", 0))
                out["skipped"] += int(s.get("skipped", 0))
        except Exception:
            continue
    return out


def build_mail(args, cfg) -> tuple[str, str]:
    status = (args.status or os.environ.get("BUILD_STATUS") or "UNKNOWN").upper()
    job = args.job or os.environ.get("JOB_NAME", "mall-cicd")
    build = args.build or os.environ.get("BUILD_NUMBER", "0")
    duration = args.duration if args.duration is not None else float(os.environ.get("BUILD_DURATION", 0) or 0)
    url = args.url or os.environ.get("BUILD_URL", "")

    ok = status == "SUCCESS"
    icon = "✅" if ok else "❌"
    color = "#1a7f37" if ok else "#cf222e"
    title = f"[{icon} {status}] mall 商城测试 · {job} #{build}"

    res = summarize_results()
    cases_line = ""
    if res["total"]:
        passed = res["total"] - res["failures"] - res["skipped"]
        cases_line = f"<li>用例：共 {res['total']} 条，通过 {passed}，失败 {res['failures']}，跳过 {res['skipped']}</li>"

    body_extra = ""
    if not ok:
        body_extra = ("<p style='color:#cf222e'><b>处理建议</b>：查看报告中的失败用例与堆栈，"
                      "确认是否为偶发（下单链路对 DB/Redis 状态敏感），必要时重跑。</p>")

    report_url = f"{url}allure/" if url else "reports/allure-report/index.html"
    html = f"""<html><body style="font-family:微软雅黑,Arial,sans-serif;color:#222">
<h3 style="color:{color}">{icon} mall 商城测试流水线 · {status}</h3>
<ul>
  <li>任务：{job}</li>
  <li>构建号：#{build}</li>
  <li>状态：<b style="color:{color}">{status}</b></li>
  <li>耗时：{fmt_duration(duration)}</li>
  {cases_line}
  <li>时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</li>
</ul>
{body_extra}
<p>构建日志：<a href="{url}console">{url}console</a><br/>
Allure 报告：<a href="{report_url}">{report_url}</a></p>
<hr style="border:none;border-top:1px solid #ddd"/>
<p style="color:#888;font-size:12px">本邮件由 mall 测试流水线自动发送（jenkins/notify.py）。</p>
</body></html>"""
    return title, html


def should_send(status: str, mode: str) -> bool:
    if mode == "fail-only":
        return status != "SUCCESS"
    if mode == "daily":
        return True
    # auto：失败必发；成功不发（由每日定时任务带 --daily 触发汇总）
    return status != "SUCCESS"


def send_mail(cfg: dict, title: str, html: str) -> dict:
    host, port = cfg["smtp_host"], int(cfg["smtp_port"])
    user, pwd = cfg["smtp_user"], cfg["smtp_pass"]
    sender = cfg["mail_from"] or user
    to_list = [x.strip() for x in str(cfg["mail_to"]).split(",") if x.strip()]

    if not host or not user or not pwd or not to_list:
        return {"sent": False, "reason": "未配置完整 SMTP 参数（host/user/pass/to）"}

    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(title, "utf-8")
    msg["From"] = Header(f"mall 测试流水线 <{sender}>", "utf-8")
    msg["To"] = ", ".join(to_list)
    msg.attach(MIMEText(html, "html", "utf-8"))

    security = str(cfg["smtp_security"]).lower()
    if security == "ssl":
        ctx = ssl.create_default_context()
        server = smtplib.SMTP_SSL(host, port, timeout=20, context=ctx)
    else:
        server = smtplib.SMTP(host, port, timeout=20)
        if security == "starttls":
            server.starttls(context=ssl.create_default_context())

    with server:
        server.login(user, pwd)
        server.sendmail(sender, to_list, msg.as_string())
    return {"sent": True, "to": to_list, "host": host, "port": port}


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", default="")
    ap.add_argument("--job", default="")
    ap.add_argument("--build", default="")
    ap.add_argument("--duration", type=float, default=None)
    ap.add_argument("--url", default="")
    ap.add_argument("--mode", default="")
    ap.add_argument("--daily", action="store_true", help="每日成功汇总：成功也发送")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    mode = args.mode or cfg["notify_mode"] or "auto"
    if args.daily:
        mode = "daily"

    status = (args.status or os.environ.get("BUILD_STATUS") or "UNKNOWN").upper()
    title, html = build_mail(args, cfg)
    record = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "status": status, "mode": mode, "title": title,
        "config": {k: ("***" if k == "smtp_pass" else v) for k, v in cfg.items()},
    }

    if not should_send(status, mode):
        record["sent"] = False
        record["reason"] = f"当前模式 {mode} 下不发送（成功构建不打扰）"
        print(json.dumps(record, ensure_ascii=False, indent=2))
    elif args.dry_run:
        record["sent"] = False
        record["reason"] = "dry-run，仅打印"
        print(title)
        print(html)
        print(json.dumps(record, ensure_ascii=False, indent=2))
    else:
        try:
            result = send_mail(cfg, title, html)
            record.update(result)
            print(json.dumps(record, ensure_ascii=False, indent=2))
        except Exception as e:
            record.update({"sent": False, "error": str(e)})
            print(json.dumps(record, ensure_ascii=False, indent=2))
            # 通知失败不影响流水线结果
            LOG = LOG_FILE
            LOG.parent.mkdir(parents=True, exist_ok=True)
            with LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            return 0

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
