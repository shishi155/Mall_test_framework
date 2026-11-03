# -*- coding: utf-8 -*-
"""从 pytest 用例源码中收集用例元数据，生成 Excel 用例台账的原始数据。

为什么这样做：
- 用例编号、标题、所属模块、自动化用例 ID 全部以代码为唯一事实来源，避免 Excel 与代码脱节；
- 前置条件/测试数据/步骤/预期结果由「模块默认值 + OVERRIDES 精修」合成，
  P0 与缺陷相关用例必须人工精修（见 OVERRIDES）。

用法: python collect_cases.py            # 打印统计并以 JSON 落盘到 build/cases.json
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"
OUT = ROOT / "build" / "cases.json"

SIDE_MAP = {"admin": "后台", "portal": "前台", "security": "跨端", "excel": "跨端", "ui": "后台"}

MODULE_MAP = {
    "test_admin_auth.py": ("登录认证", "后台-登录与权限"),
    "test_admin_product.py": ("商品管理", "后台-商品管理"),
    "test_admin_order.py": ("订单管理", "后台-订单管理"),
    "test_admin_rbac.py": ("角色权限", "后台-角色权限"),
    "test_admin_marketing.py": ("营销与基础数据", "后台-营销与基础数据"),
    "test_portal_sso.py": ("注册登录", "前台-注册登录"),
    "test_portal_product.py": ("商品浏览", "前台-商品浏览"),
    "test_portal_cart.py": ("购物车", "前台-购物车"),
    "test_portal_address.py": ("收货地址", "前台-收货地址"),
    "test_portal_order.py": ("订单", "前台-订单"),
    "test_portal_member.py": ("会员中心", "前台-会员中心"),
    "test_portal_coupon.py": ("优惠券", "前台-优惠券"),
    "test_portal_home_brand.py": ("首页与品牌", "前台-首页与品牌"),
    "test_portal_search.py": ("搜索", "前台-搜索"),
    "test_ui_smoke.py": ("UI 冒烟", "后台-UI 冒烟"),
    "test_security.py": ("安全专项", "安全专项"),
    "test_point_cases.py": ("单接口校验点", "Excel 驱动"),
}

# 预期结果精修表：P0 / 缺陷相关 / 关键链路必须写清可判定结果
OVERRIDES: Dict[str, Dict[str, str]] = {
    # ---- 后台登录 ----
    "MALL-ADM-SSO-001": {"pre": "环境就绪，内置管理员 admin 存在", "data": "admin / macro123",
                         "exp": 'code=200；data.token 为三段式 JWT；tokenHead="Bearer "；响应 <2s'},
    "MALL-ADM-SSO-002": {"pre": "管理员 admin 存在", "data": "admin / Wrong@123456",
                         "exp": 'code=500；message="密码不正确"；data=null；不返回 token（提示不一致见 D-05）'},
    "MALL-ADM-SSO-003": {"pre": "—", "data": "not_exist_9527 / Wrong@123456",
                         "exp": "两种失败场景的 code 与 message 完全一致（当前不一致 → D-05）"},
    "MALL-ADM-SSO-004": {"pre": "—", "data": 'username=""，password=macro123',
                         "exp": 'code=404；message 含 "must not be empty"；不返回 token'},
    "MALL-ADM-AUTH-001": {"pre": "未携带 token", "data": "无 Authorization 头",
                          "exp": 'code=401；message="暂未登录或token已经过期"；无业务数据'},
    "MALL-ADM-AUTH-002": {"pre": "—", "data": "Authorization: Bearer faketoken123",
                          "exp": "code=401；响应不含异常堆栈"},
    # ---- 商品 ----
    "MALL-ADM-PRD-001": {"pre": "后台已登录", "data": "pageNum=1,pageSize=5",
                         "exp": "code=200；total 等于库中 delete_status=0 的商品数；单页 ≤5 条"},
    "MALL-ADM-PRD-007": {"pre": "后台已登录，商品未删除", "data": "任一商品 id，publishStatus 0/1",
                         "exp": "code=200；库中 publish_status 与提交值一致；用例结束恢复原值"},
    "MALL-ADM-PRD-010": {"pre": "后台已登录", "data": "任一商品 id，deleteStatus=1",
                         "exp": "code=200；库中 delete_status=1；列表不再返回该商品；用例结束恢复"},
    # ---- 前台注册登录 ----
    "MALL-POR-SSO-001": {"pre": "手机号未注册", "data": "手机号=139+时间戳后8位，密码 Test@1234",
                         "exp": 'code=200 "注册成功"；库中新增 1 条 ums_member；password 为 $2a$ 开头 60 位 BCrypt 密文'},
    "MALL-POR-SSO-002": {"pre": "手机号已注册", "data": "已注册手机号",
                         "exp": "code≠200；库中该手机号仍只有 1 条记录"},
    "MALL-POR-SSO-003": {"pre": "已获取过验证码", "data": "authCode=000000",
                         "exp": "code≠200；库中不新增会员"},
    "MALL-POR-SSO-004": {"pre": "会员已注册", "data": "注册时的账号密码",
                         "exp": 'code=200；data.token 非空；data.tokenHead="Bearer "'},
    "MALL-POR-SSO-005": {"pre": "服务可用", "data": "任意手机号",
                         "exp": "接口不返回明文验证码（当前直接返回 6 位数字 → D-01）"},
    # ---- 商品浏览 ----
    "MALL-POR-PRD-001": {"pre": "商品已上架且有库存", "data": "productId 从库中动态取",
                         "exp": "code=200；详情含该商品；SKU 库存与 pms_sku_stock 一致"},
    "MALL-POR-PRD-002": {"pre": "—", "data": "productId=999999",
                         "exp": "HTTP 200 + 业务失败码并提示商品不存在（当前 HTTP500 + code401 → D-02）"},
    "MALL-POR-PRD-003": {"pre": "商品库已初始化", "data": "keyword=手机，pageSize=5",
                         "exp": "code=200；total>0；单页 ≤5 条且每条含 id/name"},
    # ---- 购物车 ----
    "MALL-POR-CART-001": {"pre": "会员已登录，购物车为空", "data": "可售商品 skuId，quantity=1",
                          "exp": "code=200；列表包含该 skuId 且 quantity=1、deleteStatus=0；促销接口带出 realStock"},
    "MALL-POR-CART-002": {"pre": "未登录", "data": "有效 productId/skuId",
                          "exp": "code=401；购物车无新增"},
    "MALL-POR-CART-003": {"pre": "已登录", "data": "同一 SKU 先 1 件再加 2 件",
                          "exp": "列表 quantity 累计为 3（同一行累加，不新增重复行）"},
    # ---- 地址 ----
    "MALL-POR-ADDR-001": {"pre": "会员已登录", "data": "广东省/深圳市/南山区 + 13800000000",
                          "exp": "code=200；ums_member_receive_address 落库且归属当前会员"},
    "MALL-POR-ADDR-006": {"pre": "已有默认地址", "data": "再新增一条 defaultStatus=1",
                          "exp": "同一会员仅一条 defaultStatus=1（当前出现 2 条 → D-08）"},
    "MALL-POR-ADDR-008": {"pre": "已登录", "data": "缺 name/phoneNumber",
                          "exp": "参数校验失败，不入库（当前仍入库 → D-07）"},
    # ---- 下单链路 ----
    "MALL-POR-ORD-001": {"pre": "已下单前状态：购物车有 2 件可下单商品", "data": "cartIds，qty=2",
                         "exp": "确认单含 cartPromotionItemList/地址/calcAmount；totalAmount=单价×2；payAmount=total-促销-运费"},
    "MALL-POR-ORD-004": {"pre": "已加购、已设默认地址", "data": "orderParam（地址 id + cartIds）",
                         "exp": "code=200；orderSn 非空；status=0；oms_order 落库且 pay_amount 与确认单一致；明细条数一致"},
    "MALL-POR-ORD-005": {"pre": "SKU 库存充足", "data": "qty=1",
                         "exp": "下单后 pms_sku_stock.lock_stock +1，stock 不变"},
    "MALL-POR-ORD-009": {"pre": "使用无促销商品", "data": "promotion_type=0 的商品",
                         "exp": "无优惠商品也能正常下单（当前 NPE → D-06）"},
    "MALL-POR-ORD-013": {"pre": "存在待付款订单", "data": "orderId + payType=0",
                         "exp": "code=200；oms_order.status=1；payment_time 非空"},
    "MALL-POR-ORD-016": {"pre": "存在待付款订单", "data": "orderId",
                         "exp": "code=200；status 由 0→4；lock_stock 回滚 -1"},
    "MALL-POR-ORD-017": {"pre": "订单已支付", "data": "orderId",
                         "exp": "已支付订单不允许用户取消（当前仍可取消 → D-09）"},
    "MALL-POR-ORD-019": {"pre": "A 会员订单，B 会员 token", "data": "他人 orderId",
                         "exp": "拒绝操作且订单状态不变（当前可取消他人订单 → D-10）"},
    "MALL-POR-ORD-012": {"pre": "A 会员订单，B 会员查询", "data": "他人 orderId",
                         "exp": "拒绝访问（当前返回 200 越权可见 → D-11）"},
    "MALL-POR-ORD-021": {"pre": "订单已取消", "data": "orderId",
                         "exp": "删除后订单不可再查询（当前仍可查 → D-12）"},
    "MALL-POR-ORD-023": {"pre": "已登录", "data": "cartIds=[]",
                         "exp": "参数校验失败并提示（当前 500 + SQL 语法错误泄露 → D-14）"},
    # ---- 后台订单 ----
    "MALL-ADM-ORD-004": {"pre": "存在 status=1 的已支付订单", "data": "orderId + 顺丰单号",
                         "exp": "code=200；status=2；delivery_company/delivery_sn 落库"},
    "MALL-ADM-ORD-006": {"pre": "存在 status=0 的订单", "data": "orderId + note=测试关闭",
                         "exp": "code=200；status=4；oms_order_operate_history 记录备注"},
    # ---- 安全 ----
    "MALL-SEC-001": {"pre": "未登录", "data": "新管理员账号",
                     "exp": "未登录不能注册后台账号（当前可直接注册 → D-15）"},
    "MALL-SEC-002": {"pre": "持有前台会员 token", "data": "portal token 访问 /admin/list",
                     "exp": "code=401，前后台密钥隔离有效"},
    "MALL-SEC-003": {"pre": "持有有效后台 token", "data": "篡改 JWT payload 的 sub",
                     "exp": "code=401，签名校验生效"},
    "MALL-SEC-006": {"pre": "—", "data": "username=admin' OR '1'='1",
                     "exp": "登录失败；响应不含 SQL 语法错误"},
    "MALL-SEC-009": {"pre": "未登录", "data": "/actuator/env 等",
                     "exp": "敏感端点不匿名暴露（非 200 或需鉴权）"},
    "MALL-SEC-013": {"pre": "—", "data": "连续 6 次错误密码",
                     "exp": "第 4 次起出现锁定/验证码等防护（当前无任何防护 → D-16）"},
    "MALL-SEC-016": {"pre": "—", "data": "Origin: https://evil.example.com",
                     "exp": "不放行任意来源（当前回显任意 Origin → D-17）"},
}

TYPE_RULES = [
    ("未登录", "权限"), ("拦截", "权限"), ("越权", "安全"), ("注入", "安全"),
    ("失败", "功能-逆向"), ("错误", "功能-逆向"), ("不存在", "功能-逆向"), ("应被", "功能-逆向"),
    ("不应", "安全"), ("泄露", "安全"), ("一致", "数据一致性"), ("落库", "数据一致性"),
]

# 未精修用例的预期结果模板（按用例类型）
EXP_TEMPLATE = {
    "权限": "返回 401（未登录）或 403（无权限），不返回任何业务数据",
    "安全": "无安全缺陷：请求被拒绝，或响应不含 SQL 报错/异常堆栈/密码等敏感信息",
    "功能-逆向": "返回业务失败码（非 200），相关数据不被写入或状态不变",
    "参数校验": "返回参数校验失败，提示可读，数据不入库",
    "数据一致性": "接口返回值与数据库记录一致（数量/金额/状态逐项比对）",
    "状态迁移": "状态按预期流转，非法迁移被拒绝",
    "功能-正向": "code=200；关键字段非空且符合接口契约，必要时与库中数据一致",
}


def _first_api(node: ast.AST) -> str:
    """取函数体里第一个以 / 开头的路径字面量。"""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str) and sub.value.startswith("/"):
            return sub.value
    return ""


def _decorator_text(node: ast.FunctionDef, name: str) -> str:
    for dec in node.decorator_list:
        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr == name:
            if dec.args and isinstance(dec.args[0], ast.Constant):
                return str(dec.args[0].value)
    return ""


def _markers(node: ast.FunctionDef) -> List[str]:
    out = []
    for dec in node.decorator_list:
        if isinstance(dec, ast.Attribute) and isinstance(dec.value, ast.Attribute):
            if dec.value.attr == "mark":
                out.append(dec.attr)
    return out


def collect() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for py in sorted(TESTS.rglob("*.py")):
        if py.name == "__init__.py":
            continue
        side_dir = py.parent.name if py.parent != TESTS else ""
        tree = ast.parse(py.read_text(encoding="utf-8-sig"))
        module, feature = MODULE_MAP.get(py.name, (py.stem, py.stem))
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
                continue
            case_id = ""
            xfail_reason = ""
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call):
                    if getattr(dec.func, "attr", "") == "case_id" and dec.args:
                        case_id = str(getattr(dec.args[0], "value", ""))
                    if getattr(dec.func, "attr", "") == "xfail":
                        for kw in dec.keywords:
                            if kw.arg == "reason" and isinstance(kw.value, ast.Constant):
                                xfail_reason = str(kw.value.value)
            if not case_id:
                continue

            markers = _markers(node)
            title = _decorator_text(node, "title") or node.name.replace("test_", "").replace("_", " ")
            story = _decorator_text(node, "story")
            api = _first_api(node)

            case_type = "功能-正向"
            for kw, t in TYPE_RULES:
                if kw in title:
                    case_type = t
                    break
            if "security" in markers:
                case_type = "安全"
            if "point" in markers:
                case_type = "功能-正向"

            CORE_MODULES = {"注册登录", "登录认证", "购物车", "订单"}
            priority = "P1"
            if ("smoke" in markers or "成功" in title or "主流程" in title
                    or (module in CORE_MODULES and case_type == "功能-正向")):
                priority = "P0"
            elif case_type in ("功能-逆向", "参数校验"):
                priority = "P2"
            elif "point" in markers:
                priority = "P2"
            elif "列表" in title or "查询" in title:
                priority = "P2"

            side = SIDE_MAP.get(side_dir, "跨端")
            override = OVERRIDES.get(case_id, {})
            rows.append({
                "case_id": case_id,
                "side": side,
                "module": module,
                "sub": story or module,
                "title": title,
                "type": case_type,
                "method": "场景法" if case_type.startswith("功能") else ("错误推测" if case_type == "安全" else "等价类"),
                "priority": priority,
                "pre": override.get("pre", "后台已登录" if side == "后台" else ("会员已登录" if "未登录" not in title else "不携带 token")),
                "data": override.get("data", "见用例实现（运行时构造）"),
                "steps": f"1. 调用 {api or '相关接口'}\n2. 校验业务码与数据\n3. 必要时查库比对",
                "exp": override.get("exp") or EXP_TEMPLATE.get(case_type, EXP_TEMPLATE["功能-正向"]),
                "api": api,
                "auto_id": f"{py.relative_to(ROOT).as_posix()}::{node.name}",
                "auto_status": "已实现",
                "defect": xfail_reason,
            })
    return rows


def main():
    rows = collect()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    from collections import Counter
    print(f"collected {len(rows)} cases")
    print("by side:", dict(Counter(r["side"] for r in rows)))
    print("by module:", dict(Counter(r["module"] for r in rows)))
    print("by priority:", dict(Counter(r["priority"] for r in rows)))
    print("with defect:", sum(1 for r in rows if r["defect"]))
    print("missing exp:", sum(1 for r in rows if not r["exp"]))


if __name__ == "__main__":
    main()
