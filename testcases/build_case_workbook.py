# -*- coding: utf-8 -*-
"""生成 mall 商城测试用例工作簿（V1.0 · 全量）。

数据来源（唯一事实来源）：
  1. build/cases.json —— 由 testcases/collect_cases.py 从 tests/ 源码解析生成（用例编号/标题/模块/自动化ID/缺陷关联）
  2. 本文件内的 DEFECTS / POINT_CASES / TEST_DATA —— 缺陷台账、Excel 驱动数据、测试数据池

用法:
  python testcases/collect_cases.py     # 先刷新 build/cases.json
  python testcases/build_case_workbook.py
输出: testcases/mall_测试用例_v1.0.xlsx
"""
from __future__ import annotations

import json
from collections import Counter, OrderedDict
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "defects"))

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
CASES_JSON = ROOT / "build" / "cases.json"
OUT = BASE / "mall_测试用例_v1.1.xlsx"

C_HEAD = "1F3864"
F_TITLE = Font(name="微软雅黑", size=14, bold=True, color="FFFFFF")
F_HEAD = Font(name="微软雅黑", size=10, bold=True, color="FFFFFF")
F_BODY = Font(name="微软雅黑", size=9)
F_SECTION = Font(name="微软雅黑", size=11, bold=True, color=C_HEAD)
FILL_TITLE = PatternFill("solid", fgColor=C_HEAD)
FILL_HEAD = PatternFill("solid", fgColor="2E5496")
FILL_SECTION = PatternFill("solid", fgColor="D9E2F3")
FILL_ZEBRA = PatternFill("solid", fgColor="F7F9FC")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
ALIGN_C = Alignment(horizontal="center", vertical="center", wrap_text=True)
ALIGN_L = Alignment(horizontal="left", vertical="top", wrap_text=True)

PRI_FILL = {
    "P0": (PatternFill("solid", fgColor="FFC7CE"), Font(name="微软雅黑", size=9, bold=True, color="9C0006")),
    "P1": (PatternFill("solid", fgColor="FFEB9C"), Font(name="微软雅黑", size=9, bold=True, color="9C6500")),
    "P2": (PatternFill("solid", fgColor="E2EFDA"), Font(name="微软雅黑", size=9, color="375623")),
    "P3": (PatternFill("solid", fgColor="F2F2F2"), Font(name="微软雅黑", size=9, color="595959")),
}

CASE_HEADERS = ["用例编号", "所属端", "模块", "子模块", "用例标题", "用例类型", "设计方法", "优先级",
                "前置条件", "测试数据", "操作步骤", "预期结果", "关联接口", "自动化状态",
                "自动化用例ID", "缺陷关联", "备注"]
CASE_WIDTHS = [20, 7, 11, 12, 34, 12, 10, 7, 26, 24, 34, 42, 26, 10, 40, 34, 18]

from build_defect_report import DEFECTS  # noqa: E402  缺陷台账与缺陷报告同源（defects/build_defect_report.py）

POINT_CASES = [
    ("MALL-ADM-SSO-001", "admin.login", "POST", "/admin/login", "JSON",
     '{"username":"admin","password":"macro123"}', "否", 200, "操作成功", "是", "登录成功金路径"),
    ("MALL-ADM-SSO-002", "admin.login", "POST", "/admin/login", "JSON",
     '{"username":"admin","password":"Wrong@123456"}', "否", 500, "密码不正确", "否", "密码错误（实测 500）"),
    ("MALL-ADM-SSO-004", "admin.login", "POST", "/admin/login", "JSON",
     '{"username":"","password":"macro123"}', "否", 404, "must not be empty", "否", "参数校验"),
    ("MALL-ADM-AUTH-001", "admin.list", "GET", "/admin/list", "Query",
     '{"pageNum":1,"pageSize":5}', "否", 401, "暂未登录", "否", "未登录拦截"),
    ("MALL-ADM-AUTH-003", "admin.info", "GET", "/admin/info", "-",
     "{}", "是", 200, "操作成功", "是", "登录后取当前用户"),
    ("MALL-ADM-PRD-001", "admin.product.list", "GET", "/product/list", "Query",
     '{"pageNum":1,"pageSize":5}', "是", 200, "操作成功", "是", "商品分页"),
    ("MALL-POR-HOME-001", "portal.home.content", "GET", "/home/content", "-",
     "{}", "否", 200, "操作成功", "是", "首页聚合"),
    ("MALL-POR-PRD-001", "portal.product.detail", "GET", "/product/detail/{id}", "Query",
     '{"id":1}', "否", 200, "操作成功", "是", "路径参数取 params.id"),
    ("MALL-POR-PRD-004", "portal.product.search", "GET", "/product/search", "Query",
     '{"keyword":"","pageNum":1,"pageSize":5}', "否", 200, "操作成功", "是", "空关键字边界"),
    ("MALL-POR-SRC-001", "portal.product.search", "GET", "/product/search", "Query",
     '{"keyword":"手机","pageNum":1,"pageSize":3}', "否", 200, "操作成功", "是", "关键字命中"),
    ("MALL-POR-SSO-001", "portal.authCode", "GET", "/sso/getAuthCode", "Query",
     '{"telephone":"13700000001"}', "否", 200, "获取验证码成功", "是", "注册前置步骤"),
    ("MALL-POR-CART-002", "portal.cart.add", "POST", "/cart/add", "JSON",
     '{"productId":26,"productSkuId":110,"quantity":1}', "否", 401, "暂未登录", "否", "未登录加购拦截"),
    ("MALL-POR-CART-004", "portal.cart.list", "GET", "/cart/list", "-",
     "{}", "否", 401, "暂未登录", "否", "未登录查购物车拦截"),
    ("MALL-POR-ORD-003", "portal.order.list", "GET", "/order/list", "Query",
     '{"status":0}', "否", 401, "暂未登录", "否", "未登录查订单拦截"),
]

TEST_DATA = [
    ("ADM-01", "后台账号", "username / password", "admin / macro123", "内置超级管理员，冒烟与回归共用", "ADM-SSO-001"),
    ("ADM-02", "后台账号", "username", "not_exist_9527", "不存在账号，用于防枚举校验", "ADM-SSO-003"),
    ("POR-01", "前台会员", "phone", "139 + 时间戳后8位（运行时生成）", "保证唯一，避免重复注册冲突", "POR-SSO-001"),
    ("POR-01", "前台会员", "username / password", "auto_<时间戳> / Test@1234", "与手机号同步生成", "POR-SSO-001"),
    ("POR-02", "商品（加购）", "productId / skuId", "27 / 98（由 DB 动态选取）", "id=1 的商品已删除且无 SKU，禁止写死", "POR-CART-001"),
    ("POR-03", "商品（下单）", "productId / skuId", "26 / 110（promotion_type=1 且有促销价）", "无优惠商品下单会 NPE（D-06），下单链路必须用促销商品", "POR-ORD-004"),
    ("POR-04", "收货地址", "name/phone/region", "自动化测试 / 13800000000 / 广东省-深圳市-南山区", "每个 shoper 夹具自动创建并绑定", "POR-ORD-004"),
    ("POR-05", "订单", "orderId / orderSn", "下单响应中获取", "订单号由 Redis 自增生成，不可预置", "POR-ORD-010"),
    ("POR-06", "优惠券", "couponId", "sms_coupon 中 perLimit=1 的券", "重复领取校验需限领 1 张的券", "POR-CPN-002"),
    ("DB-01", "数据库", "dsn", "root/Root@123456@127.0.0.1:13306/mall", "接口与库双向校验", "ADM-PRD-001"),
    ("API-01", "服务地址", "admin/portal/web", "18080 / 8085 / 8090", "容器端口映射，见环境手册", "全部"),
]


def style_header(ws, row, ncols, height=32):
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = F_HEAD
        cell.fill = FILL_HEAD
        cell.alignment = ALIGN_C
        cell.border = BORDER
    ws.row_dimensions[row].height = height


def load_cases():
    if not CASES_JSON.exists():
        raise SystemExit(f"缺少 {CASES_JSON}，请先运行 testcases/collect_cases.py")
    return json.loads(CASES_JSON.read_text(encoding="utf-8"))


def build_detail(wb, cases):
    ws = wb.create_sheet("用例详情")
    ws.sheet_properties.tabColor = "2E5496"
    n = len(CASE_HEADERS)

    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n)
    t = ws.cell(row=1, column=1, value=f"mall 商城项目 · 测试用例台账（V1.1 · 共 {len(cases)} 条自动化用例）")
    t.font = F_TITLE
    t.fill = FILL_TITLE
    t.alignment = ALIGN_C
    ws.row_dimensions[1].height = 34

    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=n)
    sub = ws.cell(row=2, column=1, value=(
        "说明：本表由 tests/ 源码自动收集生成（testcases/collect_cases.py），"
        "用例编号与自动化用例 ID 双向可追溯；「缺陷关联」列对应「缺陷线索」页，"
        "标记为 xfail 的用例断言的是正确行为、当前系统不满足。"))
    sub.font = Font(name="微软雅黑", size=9, color="404040")
    sub.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    ws.row_dimensions[2].height = 30

    for i, h in enumerate(CASE_HEADERS, start=1):
        ws.cell(row=3, column=i, value=h)
    style_header(ws, 3, n)

    for r, c in enumerate(cases, start=4):
        values = [c["case_id"], c["side"], c["module"], c["sub"], c["title"], c["type"], c["method"],
                  c["priority"], c["pre"], c["data"], c["steps"], c["exp"], c["api"],
                  c["auto_status"], c["auto_id"], c["defect"], ""]
        for i, v in enumerate(values, start=1):
            cell = ws.cell(row=r, column=i, value=v)
            cell.font = F_BODY
            cell.border = BORDER
            cell.alignment = ALIGN_L if i in (5, 9, 10, 11, 12, 13, 15, 16) else ALIGN_C
            if r % 2 == 1:
                cell.fill = FILL_ZEBRA
        pri = c["priority"]
        if pri in PRI_FILL:
            fill, font = PRI_FILL[pri]
            ws.cell(row=r, column=8).fill = fill
            ws.cell(row=r, column=8).font = font
        ws.row_dimensions[r].height = 52

    for i, w in enumerate(CASE_WIDTHS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    last = 3 + len(cases)
    ws.freeze_panes = "E4"
    ws.auto_filter.ref = f"A3:{get_column_letter(n)}{last}"

    dv_pri = DataValidation(type="list", formula1='"P0,P1,P2,P3"', allow_blank=True)
    dv_status = DataValidation(type="list", formula1='"已实现,未实现,不自动化"', allow_blank=True)
    for dv, col in ((dv_pri, "H"), (dv_status, "N")):
        ws.add_data_validation(dv)
        dv.add(f"{col}4:{col}{last + 100}")
    return ws


def build_readme(wb, cases):
    ws = wb.create_sheet("说明", 0)
    ws.sheet_properties.tabColor = "C00000"
    ws.column_dimensions["A"].width = 20
    ws.column_dimensions["B"].width = 26
    ws.column_dimensions["C"].width = 92

    ws.merge_cells("A1:C1")
    t = ws["A1"]
    t.value = "测试用例工作簿 · 使用说明（V1.0）"
    t.font = F_TITLE
    t.fill = FILL_TITLE
    t.alignment = ALIGN_C
    ws.row_dimensions[1].height = 34

    by_side = Counter(c["side"] for c in cases)
    by_pri = Counter(c["priority"] for c in cases)
    defects = len(DEFECTS)
    rows = [
        ("SECTION", "文档信息"),
        ("项目", "mall 商城（Spring Boot 3.5.14 / JDK 17）", ""),
        ("版本", "V1.1（阶段三接口 + 阶段四 UI 冒烟）", "V0.2 样例版、V1.0 纯接口版均已被本版取代"),
        ("用例总量", f"{len(cases)} 条自动化用例 + {len(POINT_CASES)} 条 Excel 驱动用例", "参数化数据页的用例由 tests/excel 执行"),
        ("分布", f"后台 {by_side.get('后台', 0)} / 前台 {by_side.get('前台', 0)} / 跨端 {by_side.get('跨境', 0) + by_side.get('跨端', 0)}", ""),
        ("优先级", f"P0 {by_pri.get('P0', 0)} / P1 {by_pri.get('P1', 0)} / P2 {by_pri.get('P2', 0)}", "P0 覆盖 8 条主链路，回归时优先执行"),
        ("缺陷", f"{defects} 条（D-01 ~ D-17）", "对应 20 条 xfail 用例，修复后自动转 PASS"),
        ("环境", "local：前台 :8085 / 后台 :18080 / 前端 :8090 / DB :13306", "见《01-环境搭建手册》"),

        ("SECTION", "工作簿结构"),
        ("用例详情", "全量用例台账（自动生成）", "编号/模块/标题/前置/数据/步骤/预期/接口/自动化ID/缺陷关联"),
        ("参数化数据", "机读用例，直接驱动 pytest", "一行=一次接口调用，由 api/registry.py 解析执行"),
        ("测试数据", "账号、商品、地址、DB 连接等数据池", "用例中的具体值统一从这里引用"),
        ("覆盖矩阵", "端/模块 → 用例数 → 优先级 → 自动化率", "用于评审覆盖率与缺口"),
        ("缺陷线索", "D-01 ~ D-17 缺陷台账", "含复现步骤、实际/期望结果、关联用例"),

        ("SECTION", "用例编号规则"),
        ("MALL-ADM-XXX-NNN", "后台管理端", "例：MALL-ADM-ORD-004（发货）"),
        ("MALL-POR-XXX-NNN", "前台商城端", "例：MALL-POR-ORD-004（下单）"),
        ("MALL-SEC-XXX-NNN", "安全专项", "例：MALL-SEC-013（爆破防护）"),
        ("MALL-UI-XXX-NNN", "Selenium UI 用例", "阶段四启用"),
        ("MALL-PERF-XXX-NNN", "性能场景", "阶段五启用"),

        ("SECTION", "优先级定义"),
        ("P0", "冒烟 / 阻断", "主流程不可用则版本不可发布，每次提交必跑"),
        ("P1", "核心功能", "影响主要业务但可绕过，每日回归"),
        ("P2", "一般 / 边界 / 逆向", "非主流程，版本回归"),
        ("P3", "低概率场景", "按需执行"),

        ("SECTION", "与 pytest 的映射"),
        ("自动化用例ID 列", "文件::函数名", "可直接 pytest 指定执行，如 tests/portal/test_portal_order.py::test_create_order_success"),
        ("缺陷关联 列", "xfail 原因", "用例断言正确行为，当前不满足 → 缺陷修复后自动 XPASS"),
        ("执行报告", "Allure", "reports/allure-report/index.html；Excel 不回写执行结果"),

        ("SECTION", "编写规范（评审要点）"),
        ("1. 一个用例一个判定点", "标题写清条件+动作+结果", "链路用例允许一个用例多个校验点，但必须能定位失败步骤"),
        ("2. 预期结果可判定", "带业务码/字段/数量/状态值", "禁止「显示正常」这类描述"),
        ("3. 前置条件可复现", "依赖数据由夹具或个人构造", "不写「已登录」了事，要写清账号与数据状态"),
        ("4. 数据唯一化", "手机号/用户名运行时生成", "避免重复执行互相污染"),
        ("5. 缺陷用 xfail 表达", "不把错误行为写成期望", "报告中 xfail 数量 = 未修复缺陷数"),
        ("6. 用例与代码同源", "Excel 由源码收集生成", "改代码后重跑 collect_cases.py 即同步，避免两张皮"),
    ]

    r = 3
    for row in rows:
        if row[0] == "SECTION":
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
            c = ws.cell(row=r, column=1, value=row[1])
            c.font = F_SECTION
            c.fill = FILL_SECTION
            c.alignment = Alignment(horizontal="left", vertical="center")
            ws.row_dimensions[r].height = 24
            for col in range(1, 4):
                ws.cell(row=r, column=col).border = BORDER
        else:
            for c, val in enumerate(row, start=1):
                cell = ws.cell(row=r, column=c, value=val)
                cell.font = F_BODY
                cell.border = BORDER
                cell.alignment = ALIGN_L
            ws.cell(row=r, column=1).font = Font(name="微软雅黑", size=9, bold=True)
            ws.row_dimensions[r].height = 28
        r += 1
    return ws


def build_points(wb):
    ws = wb.create_sheet("参数化数据")
    ws.sheet_properties.tabColor = "7030A0"
    headers = ["用例编号", "接口标识", "方法", "路径", "传参方式", "参数(JSON)", "携带token",
               "期望code", "期望message包含", "期望data非空", "备注"]
    for i, h in enumerate(headers, start=1):
        ws.cell(row=1, column=i, value=h)
    style_header(ws, 1, len(headers))
    for r, row in enumerate(POINT_CASES, start=2):
        for c, val in enumerate(row, start=1):
            cell = ws.cell(row=r, column=c, value=val)
            cell.font = F_BODY
            cell.border = BORDER
            cell.alignment = ALIGN_L if c in (5, 6, 11) else ALIGN_C
        ws.row_dimensions[r].height = 24
    for i, w in enumerate([20, 22, 7, 24, 9, 46, 9, 9, 18, 11, 24], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:K{1 + len(POINT_CASES)}"
    return ws


def build_data(wb):
    ws = wb.create_sheet("测试数据")
    ws.sheet_properties.tabColor = "70AD47"
    headers = ["数据编号", "数据类别", "字段", "值", "说明", "用于用例"]
    for i, h in enumerate(headers, start=1):
        ws.cell(row=1, column=i, value=h)
    style_header(ws, 1, len(headers))
    for r, row in enumerate(TEST_DATA, start=2):
        for c, val in enumerate(row, start=1):
            cell = ws.cell(row=r, column=c, value=val)
            cell.font = F_BODY
            cell.border = BORDER
            cell.alignment = ALIGN_L
        ws.row_dimensions[r].height = 24
    for i, w in enumerate([10, 14, 22, 44, 52, 30], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    return ws


def build_matrix(wb, cases):
    ws = wb.create_sheet("覆盖矩阵")
    ws.sheet_properties.tabColor = "FFC000"
    headers = ["所属端", "模块", "用例数", "P0", "P1", "P2", "已自动化", "缺陷关联", "自动化率"]
    for i, h in enumerate(headers, start=1):
        ws.cell(row=1, column=i, value=h)
    style_header(ws, 1, len(headers))

    grouped: "OrderedDict[tuple, list]" = OrderedDict()
    for c in cases:
        grouped.setdefault((c["side"], c["module"]), []).append(c)

    r = 2
    for (side, module), items in grouped.items():
        pri = Counter(i["priority"] for i in items)
        auto = sum(1 for i in items if i["auto_status"] == "已实现")
        defect = sum(1 for i in items if i["defect"])
        values = [side, module, len(items), pri.get("P0", 0), pri.get("P1", 0), pri.get("P2", 0),
                  auto, defect, f"{auto / len(items) * 100:.0f}%"]
        for c, val in enumerate(values, start=1):
            cell = ws.cell(row=r, column=c, value=val)
            cell.font = F_BODY
            cell.border = BORDER
            cell.alignment = ALIGN_C if c > 2 else ALIGN_L
        ws.row_dimensions[r].height = 22
        r += 1

    pri = Counter(i["priority"] for i in cases)
    auto = sum(1 for i in cases if i["auto_status"] == "已实现")
    defect = sum(1 for i in cases if i["defect"])
    totals = ["合计", f"{len(grouped)} 个模块", len(cases), pri.get("P0", 0), pri.get("P1", 0), pri.get("P2", 0),
              auto, defect, f"{auto / len(cases) * 100:.0f}%"]
    for c, val in enumerate(totals, start=1):
        cell = ws.cell(row=r, column=c, value=val)
        cell.font = Font(name="微软雅黑", size=9, bold=True)
        cell.fill = FILL_SECTION
        cell.border = BORDER
        cell.alignment = ALIGN_C if c > 2 else ALIGN_L
    ws.row_dimensions[r].height = 24

    for i, w in enumerate([10, 22, 9, 7, 7, 7, 10, 10, 10], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "C2"
    return ws


def build_defects(wb):
    ws = wb.create_sheet("缺陷线索")
    ws.sheet_properties.tabColor = "ED7D31"
    headers = ["编号", "严重程度", "所属模块", "缺陷标题", "复现步骤", "实际结果", "期望结果", "状态", "关联用例"]
    for i, h in enumerate(headers, start=1):
        ws.cell(row=1, column=i, value=h)
    style_header(ws, 1, len(headers))

    for r, row in enumerate(DEFECTS, start=2):
        for c, val in enumerate(row, start=1):
            cell = ws.cell(row=r, column=c, value=val)
            cell.font = F_BODY
            cell.border = BORDER
            cell.alignment = ALIGN_C if c in (1, 8) else ALIGN_L
        ws.row_dimensions[r].height = 58
    for i, w in enumerate([8, 14, 20, 40, 40, 44, 40, 14, 34], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:I{1 + len(DEFECTS)}"
    return ws


def main():
    cases = load_cases()
    wb = Workbook()
    wb.remove(wb.active)
    build_readme(wb, cases)
    build_detail(wb, cases)
    build_points(wb)
    build_data(wb)
    build_matrix(wb, cases)
    build_defects(wb)
    wb.active = 1
    wb.save(OUT)
    print(f"saved: {OUT}")
    print(f"cases={len(cases)} points={len(POINT_CASES)} defects={len(DEFECTS)}")


if __name__ == "__main__":
    main()
