# -*- coding: utf-8 -*-
"""生成 mall 缺陷报告 Word 正式版（V1.0）。

数据复用 defects/build_defect_report.py 中的 DEFECTS / EVIDENCE，保证 Excel 与 Word 同源。

用法: python defects/build_defect_docx.py
输出: defects/mall_缺陷报告_v1.0.docx
"""
from __future__ import annotations

import sys
from collections import Counter
from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
from build_defect_report import DEFECTS, ENV, EVIDENCE  # noqa: E402

OUT = BASE / "mall_缺陷报告_v1.1.docx"

SEV_COLOR = {
    "阻断": RGBColor(0xC0, 0x00, 0x00),
    "严重": RGBColor(0x9C, 0x00, 0x06),
    "主要": RGBColor(0x9C, 0x65, 0x00),
    "次要": RGBColor(0x37, 0x56, 0x23),
    "建议": RGBColor(0x59, 0x59, 0x59),
}


def set_font(doc):
    style = doc.styles["Normal"]
    style.font.name = "微软雅黑"
    style.font.size = Pt(10.5)
    style.element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
    for i in range(1, 4):
        h = doc.styles[f"Heading {i}"]
        h.font.name = "微软雅黑"
        h.element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
        h.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)


def cover(doc):
    for _ in range(6):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("mall 商城系统\n缺陷报告")
    run.font.size = Pt(30)
    run.font.bold = True
    run.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)

    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run("V1.0").font.size = Pt(16)

    for _ in range(6):
        doc.add_paragraph()

    info = [
        ("被测系统", "mall（Spring Boot 3.5.14 / JDK 17）"),
        ("测试阶段", "阶段二：接口测试　阶段三：全链路 + 安全专项"),
        ("缺陷总数", f"{len(DEFECTS)} 条"),
        ("编制", "测试组"),
        ("日期", date.today().isoformat()),
        ("密级", "内部"),
    ]
    table = doc.add_table(rows=len(info), cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, (k, v) in enumerate(info):
        table.cell(i, 0).text = k
        table.cell(i, 1).text = v
        table.cell(i, 0).paragraphs[0].runs[0].bold = True
    doc.add_page_break()


def section_overview(doc):
    doc.add_heading("一、报告概述", level=1)
    doc.add_paragraph(
        "本报告汇总 mall 商城系统在接口测试与安全专项中发现的缺陷，共计 "
        f"{len(DEFECTS)} 条。所有缺陷均来自自动化用例（pytest + Allure）与接口探测，"
        "每条缺陷都可按「复现步骤」独立复现，并附带请求/响应报文与数据库校验结果。"
    )
    doc.add_heading("1.1 测试环境", level=2)
    doc.add_paragraph(ENV)
    doc.add_heading("1.2 测试方法", level=2)
    for text in [
        "接口功能测试：pytest + requests，按业务链路（注册登录→商品→购物车→下单→支付→订单）组织用例；",
        "数据一致性校验：接口返回值与 MySQL 记录双向比对（库存锁定、订单金额、状态流转）；",
        "安全专项：认证绕过、越权（IDOR）、SQL 注入、信息泄露、防护缺失（爆破/CORS）；",
        "缺陷判定：用例断言的是「正确行为」，当前系统不满足即记缺陷，并以 xfail 固化，修复后自动转 PASS。",
    ]:
        doc.add_paragraph(text, style="List Bullet")
    doc.add_heading("1.3 用例与缺陷关系", level=2)
    doc.add_paragraph(
        "本次共执行 152 条用例（138 条业务/安全 + 14 条 Excel 驱动），通过 131 条，"
        "20 条以 xfail 形式记录 17 条未修复缺陷，1 条因测试数据受限跳过。"
    )


def section_stats(doc):
    doc.add_heading("二、缺陷统计", level=1)
    by_sev = Counter(d[3] for d in DEFECTS)
    by_mod = Counter(d[2] for d in DEFECTS)

    doc.add_heading("2.1 按严重程度", level=2)
    table = doc.add_table(rows=1, cols=3)
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    for i, t in enumerate(["严重程度", "数量", "占比"]):
        hdr[i].text = t
        hdr[i].paragraphs[0].runs[0].bold = True

    for sev in ("阻断", "严重", "主要", "次要", "建议"):
        cnt = by_sev.get(sev, 0)
        if not cnt:
            continue
        row = table.add_row().cells
        row[0].text = sev
        row[1].text = str(cnt)
        row[2].text = f"{cnt / len(DEFECTS) * 100:.0f}%"
        run = row[0].paragraphs[0].runs[0]
        run.font.bold = True
        run.font.color.rgb = SEV_COLOR.get(sev, RGBColor(0, 0, 0))

    doc.add_heading("2.2 按模块", level=2)
    table = doc.add_table(rows=1, cols=3)
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    for i, t in enumerate(["模块", "数量", "占比"]):
        hdr[i].text = t
        hdr[i].paragraphs[0].runs[0].bold = True
    for mod, cnt in by_mod.most_common():
        row = table.add_row().cells
        row[0].text = mod
        row[1].text = str(cnt)
        row[2].text = f"{cnt / len(DEFECTS) * 100:.0f}%"


def section_detail(doc):
    doc.add_heading("三、缺陷明细", level=1)
    doc.add_paragraph(
        "以下按「阻断 → 严重 → 主要 → 次要」排序。每条缺陷包含：基本信息、前置条件、复现步骤、"
        "实际结果、预期结果、业务影响、根因分析、修复建议、复现命令。"
    )

    order = {"阻断": 0, "严重": 1, "主要": 2, "次要": 3, "建议": 4}
    defects = sorted(DEFECTS, key=lambda d: (order.get(d[3], 9), d[0]))

    for d in defects:
        (did, title, module, sev, pri, dtype, status, phase,
         cases, pre, steps, actual, expect, impact, root, fix, cmd, evidence) = d

        h = doc.add_heading(f"{did}　{title}", level=2)
        run = h.runs[0]
        run.font.color.rgb = SEV_COLOR.get(sev, RGBColor(0, 0, 0))

        table = doc.add_table(rows=0, cols=2)
        table.style = "Table Grid"
        meta = [
            ("严重程度", sev), ("优先级", pri), ("缺陷类型", dtype),
            ("所属模块", module), ("状态", status), ("发现阶段", phase),
            ("关联用例", cases), ("证据编号", evidence),
        ]
        for k, v in meta:
            row = table.add_row().cells
            row[0].text = k
            row[1].text = v
            row[0].paragraphs[0].runs[0].bold = True

        for label, content in (
            ("前置条件", pre), ("复现步骤", steps), ("实际结果", actual),
            ("预期结果", expect), ("业务影响", impact), ("根因分析", root),
            ("修复建议", fix), ("复现命令", cmd),
        ):
            p = doc.add_paragraph()
            p.add_run(f"{label}：").bold = True
            run = p.add_run(content)
            if label in ("复现步骤", "实际结果", "复现命令"):
                run.font.name = "Consolas"
                run.font.size = Pt(9)

        doc.add_paragraph()


def section_conclusion(doc):
    doc.add_heading("四、结论与发布建议", level=1)
    doc.add_paragraph(
        "基于上述缺陷分布与影响面，本次版本**不建议上线**。"
        "主要理由：存在 6 条阻断级缺陷，其中 D-06 导致 18/20 在售商品无法下单，"
        "D-09/D-10/D-11 构成资金与越权风险，D-14/D-15 属于高危信息泄露与认证缺口。"
    )

    doc.add_heading("4.1 放行条件", level=2)
    for text in [
        "D-06 修复，任意商品均可下单，「无优惠商品下单」用例转 PASS；",
        "D-09 / D-10 / D-11 修复，订单操作均校验会员归属与订单状态，越权用例转 PASS；",
        "D-14 / D-15 修复，异常不再外泄 SQL，后台注册接口收敛；",
        "P0 用例 100% 通过，P1 用例通过率 ≥ 95%；",
        "回归执行 pytest -m smoke 与 pytest -m security 全绿，Allure 报告归档。",
    ]:
        doc.add_paragraph(text, style="List Number")

    doc.add_heading("4.2 风险提示", level=2)
    doc.add_paragraph(
        "D-02（异常被包装成 401）会掩盖其他缺陷的真实表现，建议优先修复，"
        "否则后续回归中大量异常将以“未登录”呈现，误导定位方向。"
    )


def section_appendix(doc):
    doc.add_heading("五、附录：复现证据索引", level=1)
    doc.add_paragraph("下表为证据编号与「缺陷编号 / 请求 / 实际响应」的对应关系，完整报文见 Excel 台账「复现证据」页。")

    table = doc.add_table(rows=1, cols=3)
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    for i, t in enumerate(["证据编号", "请求", "实际响应（摘要）"]):
        hdr[i].text = t
        hdr[i].paragraphs[0].runs[0].bold = True
    for eid, did, req, args, resp, db, note in EVIDENCE:
        row = table.add_row().cells
        row[0].text = eid
        row[1].text = req
        row[2].text = resp.replace("\n", " ")[:180]


def main():
    doc = Document()
    set_font(doc)
    for section in doc.sections:
        section.top_margin = Cm(2.2)
        section.bottom_margin = Cm(2.2)
        section.left_margin = Cm(2.4)
        section.right_margin = Cm(2.4)

    cover(doc)
    section_overview(doc)
    section_stats(doc)
    section_detail(doc)
    section_conclusion(doc)
    section_appendix(doc)

    doc.save(OUT)
    print(f"saved: {OUT}")
    print(f"defects={len(DEFECTS)} evidence={len(EVIDENCE)}")


if __name__ == "__main__":
    main()
