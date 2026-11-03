# -*- coding: utf-8 -*-
"""生成 mall 缺陷报告（V1.0）。

结构与《缺陷报告规范》一致：
  缺陷统计 / 缺陷明细（含详细复现步骤）/ 复现证据 / 报告规范

用法: python defects/build_defect_report.py
输出: defects/mall_缺陷报告_v1.0.xlsx
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

BASE = Path(__file__).resolve().parent
OUT = BASE / "mall_缺陷报告_v1.1.xlsx"

C_HEAD = "8B1A1A"
F_TITLE = Font(name="微软雅黑", size=15, bold=True, color="FFFFFF")
F_HEAD = Font(name="微软雅黑", size=10, bold=True, color="FFFFFF")
F_BODY = Font(name="微软雅黑", size=9)
F_MONO = Font(name="Consolas", size=9)
F_SECTION = Font(name="微软雅黑", size=11, bold=True, color=C_HEAD)
FILL_TITLE = PatternFill("solid", fgColor=C_HEAD)
FILL_HEAD = PatternFill("solid", fgColor="B23A3A")
FILL_SECTION = PatternFill("solid", fgColor="F2DCDB")
FILL_ZEBRA = PatternFill("solid", fgColor="FBF7F7")
THIN = Side(style="thin", color="D0C0C0")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
ALIGN_C = Alignment(horizontal="center", vertical="center", wrap_text=True)
ALIGN_L = Alignment(horizontal="left", vertical="top", wrap_text=True)

SEV_FILL = {
    "阻断": (PatternFill("solid", fgColor="C00000"), Font(name="微软雅黑", size=9, bold=True, color="FFFFFF")),
    "严重": (PatternFill("solid", fgColor="FFC7CE"), Font(name="微软雅黑", size=9, bold=True, color="9C0006")),
    "主要": (PatternFill("solid", fgColor="FFEB9C"), Font(name="微软雅黑", size=9, bold=True, color="9C6500")),
    "次要": (PatternFill("solid", fgColor="E2EFDA"), Font(name="微软雅黑", size=9, color="375623")),
    "建议": (PatternFill("solid", fgColor="EDEDED"), Font(name="微软雅黑", size=9, color="595959")),
}

ENV = ("mall local（Docker Compose）｜admin http://localhost:18080 ｜portal http://localhost:8085 ｜"
       "web http://localhost:8090 ｜MySQL 127.0.0.1:13306 / mall")

# ============ 缺陷明细 ============
# 字段: 编号, 标题, 模块, 严重, 优先级, 类型, 状态, 发现阶段, 关联用例, 前置条件, 复现步骤, 实际结果, 预期结果,
#       业务影响, 根因, 修复建议, 复现命令, 证据
DEFECTS = [
    ("D-06", "无优惠/打折/满减商品下单触发 NPE，主流程不可用", "前台-订单", "阻断", "P0", "功能-异常", "新建",
     "阶段三（接口）", "MALL-POR-ORD-009",
     "1) 后台存在 promotion_type=0/3/4 的在售商品（mall.sql 中 20 个在售商品有 18 个属于此类）\n"
     "2) 会员已登录且已设置默认收货地址",
     "1. 取一个 promotion_type=0 的商品与其 SKU：\n"
     "   SELECT s.product_id, s.id FROM pms_sku_stock s JOIN pms_product p ON p.id=s.product_id\n"
     "   WHERE p.delete_status=0 AND p.publish_status=1 AND p.promotion_type=0 LIMIT 1;\n"
     "2. POST /cart/add  body: {\"productId\":<上一步 product_id>,\"productSkuId\":<sku_id>,\"quantity\":1}\n"
     "3. GET /cart/list 取出购物车项 id（假设为 148）\n"
     "4. POST /order/generateConfirmOrder  body: [148]\n"
     "5. 观察响应与 mall-portal 日志",
     "第 4 步返回 HTTP 500，body 为 {\"code\":401,\"message\":\"暂未登录或token已经过期\"}（真实异常被安全框架掩盖）\n"
     "服务端日志：NullPointerException: Cannot invoke \"java.math.BigDecimal.multiply(java.math.BigDecimal)\" "
     "because the return value of \"CartPromotionItem.getPrice()\" is null\n"
     "at OmsPortalOrderServiceImpl.calcCartAmount(OmsPortalOrderServiceImpl.java:759)\n"
     "at OmsPortalOrderServiceImpl.generateConfirmOrder(OmsPortalOrderServiceImpl.java:88)",
     "code=200；确认单返回商品促销明细与 calcAmount；随后可正常下单",
     "除 2 个单品促销商品外，其余商品全部无法下单；前台无任何可读错误提示，用户流失且无法自助排查",
     "OmsPromotionServiceImpl.handleNoReduce()（无优惠分支）只设置 realStock/reduceAmount/integration/growth，"
     "未调用 setPrice()；打折分支（type=3）与满减分支（type=4）同样未设置 price。"
     "下游 calcCartAmount 直接 item.getPrice().multiply(...) 导致 NPE。",
     "1) handleNoReduce 及各促销分支补 cartPromotionItem.setPrice(originalPrice)；\n"
     "2) calcCartAmount 对 price 为 null 做兜底（取商品价或抛业务异常）；\n"
     "3) 配套修复 D-02，让异常不再被包装成 401。",
     "pytest tests/portal/test_portal_order.py::test_create_order_no_promotion_product -rs",
     "复现证据 E-06（含异常堆栈）"),

    ("D-09", "已支付订单可被用户直接取消，无退款流程", "前台-订单", "阻断", "P0", "业务-状态", "新建",
     "阶段三（接口）", "MALL-POR-ORD-017",
     "会员已登录，存在一笔 status=1（已支付）的订单",
     "1. 下单：POST /order/generateOrder（或复用已有订单，记 orderId）\n"
     "2. 模拟支付回调：POST /order/paySuccess?orderId=<id>&payType=0  → code=200，status 变 1\n"
     "3. 用户取消：POST /order/cancelUserOrder?orderId=<id>\n"
     "4. 查询：SELECT status, pay_amount FROM oms_order WHERE id=<id>;",
     "第 3 步返回 {\"code\":200,\"message\":\"操作成功\"}；第 4 步 status=4（已关闭），"
     "但没有任何退款单、退款金额、退款状态记录（oms_order 无 refund 相关字段变化）",
     "已支付订单不允许用户自行取消；应走售后/退款流程，由后台审核后关闭",
     "用户付款后可直接把订单置为已关闭，商品不再发货而资金仍停留在平台；对账时出现“已关闭但有收款”的异常单",
     "OmsPortalOrderServiceImpl.cancelUserOrder 只判断订单归属（部分场景），未校验 status 是否允许取消，"
     "也未触发退款/库存回滚逻辑",
     "取消前置校验只允许 status=0；status=1 需走退款申请接口；补充退款流水表与状态机",
     "pytest tests/portal/test_portal_order.py::test_cancel_paid_order -rs",
     "复现证据 E-09"),

    ("D-10", "取消订单不校验订单存在性与会员归属（可取消他人订单）", "前台-订单", "阻断", "P0", "安全-越权", "新建",
     "阶段三（接口+安全）", "MALL-POR-ORD-018 / MALL-POR-ORD-019",
     "准备两个会员 A、B；A 有一笔待付款订单（orderId=X）",
     "1. 用 A 登录下单，记 orderId=X\n"
     "2. 用 B 的 token 调用：POST /order/cancelUserOrder?orderId=X\n"
     "3. 查询：SELECT id, member_id, status FROM oms_order WHERE id=X;",
     "第 2 步返回 {\"code\":200,\"message\":\"操作成功\"}；第 3 步该订单 status=4，member_id 仍为 A\n"
     "补充：POST /order/cancelUserOrder?orderId=99999999（不存在）同样返回 code=200「操作成功」",
     "校验订单存在且属于当前会员，否则返回 403/404；状态不符合时返回业务错误",
     "任意登录用户可遍历 orderId 关闭他人订单，属于典型 IDOR 越权；结合 D-09 可造成“付款后被他人关单”",
     "cancelUserOrder 未在 SQL 条件中带 member_id，Update 影响行数为 0 时仍返回成功",
     "所有订单操作 SQL 增加 member_id=当前会员；受影响行数为 0 时返回 404/403；补充越权回归用例",
     "pytest tests/portal/test_portal_order.py::test_cancel_others_order tests/portal/test_portal_order.py::test_cancel_not_exist_order -rs",
     "复现证据 E-10"),

    ("D-11", "订单详情未校验会员归属（IDOR，可读取他人订单）", "前台-订单", "阻断", "P0", "安全-越权", "新建",
     "阶段三（接口+安全）", "MALL-POR-ORD-012",
     "准备两个会员 A、B；A 有一笔订单（orderId=X）",
     "1. 用 A 下单并记 orderId=X\n"
     "2. 用 B 的 token 调用：GET /order/detail/X\n"
     "3. 检查响应中的 receiverName / receiverPhone / totalAmount / orderItemList",
     "第 2 步返回 code=200，data 为 A 的完整订单（收货人、手机号、地址、金额、商品明细）",
     "返回 403 或空，非本人订单不可见",
     "用户隐私（收货人姓名、电话、地址）与交易信息泄露，可被批量遍历；同时暴露订单号规律（日期+自增）",
     "OmsPortalOrderServiceImpl.detail(orderId) 直接按主键查询，未附加 member_id 条件",
     "detail 查询增加 member_id 条件；对不存在/非本人统一返回 404，避免泄露订单是否存在",
     "pytest tests/portal/test_portal_order.py::test_order_detail_idor -rs",
     "复现证据 E-11"),

    ("D-14", "空购物车下单返回 500 且把 MySQL 语法错误原文返回前端", "前台-订单", "阻断", "P0", "安全-信息泄露", "新建",
     "阶段三（接口+安全）", "MALL-POR-ORD-023 / MALL-SEC-012",
     "会员已登录且已设置默认收货地址",
     "1. POST /order/generateOrder\n"
     "   body: {\"memberReceiveAddressId\":<地址id>,\"couponId\":null,\"useIntegration\":0,\"payType\":0,\"cartIds\":[]}\n"
     "2. 观察 HTTP 状态码与 message 字段",
     "HTTP 500，message 为：\n"
     "\"You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version "
     "for the right syntax to use near '' at line 6\"",
     "参数校验失败（如「请选择要结算的商品」），HTTP 200 + 业务错误码，不暴露任何 SQL/堆栈",
     "1) 未做入参校验，空集合直接拼 SQL 导致语法错误；2) 数据库异常信息直达前端，可辅助注入探测与表结构推断",
     "OrderParam.cartIds 为空时未拦截；MyBatis 动态 SQL 在空集合时生成了不完整语句；"
     "全局异常处理器把 SQLException 的 message 原样返回",
     "1) 入参校验 @NotEmpty；2) 动态 SQL 使用 <if> 保护；3) 全局异常处理对外只返回兜底文案，详细堆栈写日志",
     "pytest tests/portal/test_portal_order.py::test_create_order_empty_cart -rs",
     "复现证据 E-14"),

    ("D-15", "后台注册接口未鉴权，任意人可注册后台账号", "后台-登录认证", "阻断", "P0", "安全-认证", "新建",
     "阶段三（安全）", "MALL-SEC-001",
     "无需任何凭证（未登录）",
     "1. POST http://localhost:18080/admin/register\n"
     "   body: {\"username\":\"sec_9527\",\"password\":\"Test@1234\",\"nickName\":\"sec\"}\n"
     "2. 用该账号登录：POST /admin/login 同上账号密码\n"
     "3. 用返回的 token 访问 GET /admin/info",
     "第 1 步 code=200，注册成功；第 2 步 code=200 拿到 token；第 3 步返回该管理员信息（无任何角色资源，访问业务接口返回 403）",
     "注册接口不应对外暴露：由超管在后台创建，或需邀请码 + 限流",
     "可批量注册后台账号、占用用户名、配合爆破尝试提权；任意人能确认“这是 mall 后台”并持续探测",
     "application.yml 的 secure.ignored.urls 中包含 /admin/register",
     "从白名单移除 /admin/register；如业务需要保留，增加邀请码校验 + IP 限流 + 审计日志",
     "pytest tests/security/test_security.py::test_admin_register_requires_auth -rs",
     "复现证据 E-15"),

    ("D-01", "获取验证码接口明文返回验证码，手机号归属未校验", "前台-注册登录", "严重", "P0", "安全-认证", "新建",
     "阶段二（探索）", "MALL-POR-SSO-005",
     "无（服务可用即可）",
     "1. GET /sso/getAuthCode?telephone=13700000001\n"
     "2. 观察响应 data 字段\n"
     "3. 用该 data 直接注册：POST /sso/register?username=x&password=y&telephone=13700000001&authCode=<data>",
     "第 1 步 HTTP 200，data 为 6 位明文验证码（如 \"355860\"）；第 3 步注册成功",
     "接口只返回发送结果，验证码通过短信/邮件下发；同手机号限制发送频次与校验次数",
     "任意手机号可被注册（无需持有该手机号），可批量注册、刷券、刷单；验证码机制形同虚设",
     "UmsMemberServiceImpl.generateAuthCode 把验证码直接作为 CommonResult.success(authCode) 返回，"
     "仅写入 Redis 供后续校验，未做通道下发",
     "改为短信通道下发；接口返回固定文案；同一手机号 60s 一条、单日上限；校验失败 5 次作废",
     "pytest tests/portal/test_portal_sso.py::test_auth_code_not_returned_plaintext -rs",
     "复现证据 E-01"),

    ("D-02", "未放行 /error，异常被安全框架吞掉，返回 HTTP500 + code=401", "通用", "严重", "P1", "功能-异常", "新建",
     "阶段二（探索）", "MALL-POR-PRD-002 / MALL-POR-BRAND-003",
     "服务已启动",
     "1. GET /product/detail/999999\n"
     "2. 观察 HTTP 状态码与 body\n"
     "3. 对照日志中的真实异常",
     "HTTP 500，body 为 {\"code\":401,\"message\":\"暂未登录或token已经过期\",\"data\":\"Full authentication is required...\"}\n"
     "日志里是真实业务异常（如商品不存在 / NPE），前端完全看不到",
     "HTTP 200 + code=500/404 并给出业务提示；HTTP 状态码与业务码语义一致",
     "所有服务端异常的对外表现都变成“未登录”，前端与用户被误导，排障时间被拉长；也让 D-06 这类阻断缺陷难以被发现",
     "Spring Security 对 /error 未放行，异常转发到 /error 时被 AuthenticationEntryPoint 接管",
     "secure.ignored.urls 增加 /error；统一异常处理返回稳定结构（code/message/requestId），HTTP 状态码按语义返回",
     "pytest tests/portal/test_portal_product.py::test_product_detail_not_exist -rs",
     "复现证据 E-02"),

    ("D-13", "确认单/下单不校验购物车（空 cartIds、无效 cartId 均返回成功）", "前台-订单", "严重", "P1", "功能-参数校验", "新建",
     "阶段三（接口）", "MALL-POR-ORD-002 / MALL-POR-ORD-003",
     "会员已登录",
     "1. POST /order/generateConfirmOrder  body: []\n"
     "2. POST /order/generateConfirmOrder  body: [99999999]\n"
     "3. 观察 code 与 cartPromotionItemList",
     "两次均返回 code=200「操作成功」，data.cartPromotionItemList=[]（空明细的“成功”确认单）",
     "返回业务失败：购物车为空 / 商品不存在",
     "前端若不做二次校验会展示金额为 0 的结算页，用户可继续下一步（进而触发 D-14）",
     "generateConfirmOrder 未校验 cartIds 非空、是否存在、是否属于当前会员",
     "入参校验 + 归属校验；空集合直接返回 \"请选择要结算的商品\"",
     "pytest tests/portal/test_portal_order.py::test_confirm_order_empty_cart tests/portal/test_portal_order.py::test_confirm_order_invalid_cart_id -rs",
     "复现证据 E-13"),

    ("D-05", "登录失败提示不一致，可枚举后台账号", "后台-登录认证", "主要", "P1", "安全-信息泄露", "新建",
     "阶段二（探索）", "MALL-ADM-SSO-003",
     "无",
     "1. POST /admin/login  body: {\"username\":\"admin\",\"password\":\"Wrong@123456\"}\n"
     "2. POST /admin/login  body: {\"username\":\"not_exist_9527\",\"password\":\"Wrong@123456\"}\n"
     "3. 对比两次的 code 与 message",
     "账号存在：code=500，message=\"密码不正确\"\n账号不存在：code=404，message=\"用户名或密码错误\"\n两者可直接区分账号是否存在",
     "两种情况返回完全一致的业务码与提示（如统一 “用户名或密码错误”）",
     "可先枚举出有效后台账号，再针对性爆破（结合 D-16 无锁定，风险叠加）",
     "UmsAdminServiceImpl.login 对“用户不存在”和“密码不匹配”抛了不同的业务异常",
     "统一失败提示与业务码；失败计数 + 锁定策略；记录登录审计日志",
     "pytest tests/admin/test_admin_auth.py::test_login_user_not_exist_same_message -rs",
     "复现证据 E-05"),

    ("D-16", "后台登录无失败次数限制、无验证码，可被暴力破解", "后台-登录认证", "主要", "P1", "安全-防护缺失", "新建",
     "阶段三（安全）", "MALL-SEC-013",
     "已知有效账号（如 admin）",
     "1. 连续 6 次 POST /admin/login，密码均为错误值\n"
     "2. 第 6 次后立即用正确密码登录\n"
     "3. 检查是否有锁定提示、验证码、响应延迟",
     "6 次失败均正常返回业务错误；第 7 次用正确密码直接登录成功；无锁定、无验证码、无延迟",
     "失败 3-5 次后要求验证码或锁定账号（可配置），并记录来源 IP",
     "后台入口可被字典/撞库攻击，弱口令账号极易失守",
     "登录接口无失败计数、无限流、无验证码",
     "Redis 记录失败次数（按账号 + IP），超阈值锁定 15 分钟；接入图形/行为验证码；告警",
     "pytest tests/security/test_security.py::test_login_bruteforce_protection -rs",
     "复现证据 E-16"),

    ("D-07", "收货地址未做参数校验（缺必填项、手机号格式非法均可入库）", "前台-收货地址", "主要", "P2", "功能-参数校验", "新建",
     "阶段三（接口）", "MALL-POR-ADDR-008 / MALL-POR-ADDR-009",
     "会员已登录",
     "1. POST /member/address/add  body: {\"province\":\"广东省\",\"city\":\"深圳市\",\"region\":\"南山区\",\"detailAddress\":\"x\"}（缺 name/phoneNumber）\n"
     "2. POST /member/address/add  手机号传 \"abc123\"\n"
     "3. GET /member/address/list 查看是否入库",
     "两次均 code=200，地址成功入库；列表中可见缺收货人、手机号为 abc123 的记录",
     "必填项缺失 / 手机号格式非法 → 参数校验失败，不入库",
     "脏数据进入订单收货信息，影响后续发货与物流对接",
     "UmsMemberReceiveAddress 未加 @Validated/@NotBlank/@Pattern 校验",
     "实体加校验注解并在 Controller 加 @Validated；手机号正则校验；前端同步校验",
     "pytest tests/portal/test_portal_address.py -k required -rs",
     "复现证据 E-07"),

    ("D-08", "新增默认地址不重置旧默认，出现多条默认地址", "前台-收货地址", "次要", "P2", "功能-数据一致性", "新建",
     "阶段三（接口）", "MALL-POR-ADDR-006",
     "会员已有一条 defaultStatus=1 的地址",
     "1. 再新增一条地址，defaultStatus=1\n"
     "2. GET /member/address/list\n"
     "3. 统计 defaultStatus=1 的条数",
     "返回 2 条 defaultStatus=1 的地址（实测 id=45、46 均为默认）",
     "同一会员任何时刻只有一条默认地址，新增默认时自动取消旧默认",
     "下单时“默认地址”取值不确定，可能发货到旧地址",
     "UmsMemberReceiveAddressServiceImpl.add 未重置其他地址的 default_status",
     "新增/修改默认地址时先 UPDATE ... SET default_status=0 WHERE member_id=?；加唯一约束兜底",
     "pytest tests/portal/test_portal_address.py::test_address_default_unique -rs",
     "复现证据 E-08"),

    ("D-12", "删除订单后详情仍可查询，软删除未在查询侧生效", "前台-订单", "次要", "P2", "功能-数据一致性", "新建",
     "阶段三（接口）", "MALL-POR-ORD-021",
     "存在一笔已取消（status=4）的订单",
     "1. POST /order/deleteOrder?orderId=X\n"
     "2. GET /order/detail/X\n"
     "3. SELECT delete_status FROM oms_order WHERE id=X;",
     "第 1 步 code=200；库中 delete_status=1；但第 2 步仍返回完整订单数据",
     "删除后详情返回 404/空，列表也不可见",
     "用户以为删除了，实际数据仍可被查询；若配合 D-11 可被他人读取（已删订单也可能含隐私）",
     "deleteOrder 只更新 delete_status，detail 查询未加 delete_status=0 条件",
     "detail 查询增加 delete_status=0；删除操作返回影响行数校验",
     "pytest tests/portal/test_portal_order.py::test_delete_cancelled_order -rs",
     "复现证据 E-12"),

    ("D-03", "参数校验提示为英文，未做国际化", "后台-登录认证", "次要", "P3", "体验-文案", "新建",
     "阶段二（探索）", "MALL-ADM-SSO-004",
     "无",
     "1. POST /admin/login  body: {\"username\":\"\",\"password\":\"macro123\"}\n"
     "2. 观察 message",
     "code=404，message=\"username must not be empty\"（英文，来自 Bean Validation 默认提示）",
     "返回中文提示，如「用户名不能为空」，且提示语与前端保持一致",
     "面向中文用户的后台出现英文技术文案，体验割裂，也不利于运营自助排查",
     "@Validated 的注解未配置 message，使用了 Hibernate Validator 默认（英文）文案",
     "注解补 message=\"{用户名不能为空}\"；配置 ValidationMessages_zh_CN.properties；统一异常处理映射",
     "pytest tests/admin/test_admin_auth.py::test_login_blank_username -rs",
     "复现证据 E-03"),

    ("D-04", "HTTP 状态码与业务码不一致，全部以 HTTP 200 包装", "后台-登录认证", "次要", "P3", "设计-接口规范", "新建",
     "阶段二（探索）", "MALL-ADM-AUTH-001",
     "无 token",
     "1. 不带 Authorization 访问 GET /admin/list\n"
     "2. 观察 HTTP 状态码与 body.code",
     "HTTP 200，body 为 {\"code\":401,...}；而 D-02 的场景却是 HTTP 500 + code=401，同一语义出现两种 HTTP 状态",
     "HTTP 状态码与业务语义一致（401/403/404/500），或全局统一为 200，二者择一并写入接口规范",
     "网关、监控、前端拦截器无法按 HTTP 状态统一处理，错误统计失真",
     "全局异常处理与 Security 的入口各自返回，未统一",
     "确定接口规范（建议HTTP语义化）；在全局异常处理器统一出口；文档同步",
     "pytest tests/admin/test_admin_auth.py::test_admin_list_without_token -rs",
     "复现证据 E-04"),

    ("D-17", "CORS 使用 allowedOriginPatterns(*)，任意来源可跨域读取响应", "后台/前台", "次要", "P3", "安全-配置", "新建",
     "阶段三（安全）", "MALL-SEC-016",
     "服务已启动",
     "1. curl -H \"Origin: https://evil.example.com\" http://localhost:18080/admin/login -i\n"
     "2. 查看响应头 Access-Control-Allow-Origin",
     "响应回显 Access-Control-Allow-Origin: https://evil.example.com，任意来源被放行",
     "仅放行配置化白名单域名；生产环境禁止通配",
     "攻击者可在恶意站点发起跨域请求读取响应（当前 token 在 header 中，风险受限，但属配置缺陷）",
     "GlobalCorsConfig 使用 allowedOriginPatterns(\"*\") 且 allowCredentials(true)",
     "改为配置项注入白名单；allowCredentials 与通配不可同时开启",
     "pytest tests/security/test_security.py::test_cors_policy -rs",
     "复现证据 E-17"),

    ("U-01", "访问未定义路由时整页白屏，无 404 兜底", "后台-UI", "主要", "P2", "功能-异常", "新建",
     "阶段四（UI 冒烟）", "MALL-UI-009",
     "已登录后台，持有有效 token",
     "1. 浏览器地址栏输入 http://localhost:8090/#/pms/product/index（多写了一层 /index，真实路由是 /pms/product）\n"
     "2. 等待 5 秒\n"
     "3. 观察页面与控制台",
     "页面完全空白（<div id=\"app\"><div data-v-app=\"\"></div></div>），无任何提示；控制台也没有 404 相关日志",
     "跳转 404 页面或提示「页面不存在」并给出返回首页入口",
     "用户输错地址/收藏了旧链接时看到白屏，会认为系统故障；也不利于问题排查",
     "router 未配置 pathMatch 通配路由（只有显式 /404 页面），未匹配路由时 Layout 不渲染任何子路由",
     "增加 { path: '/:pathMatch(.*)*', redirect: '/404' }；Layout 内增加异常兜底组件",
     "pytest tests/ui/test_ui_smoke.py::test_unknown_route_fallback -rs",
     "复现证据 E-U01（含截图）"),

    ("U-02", "前端 API 无统一命名空间，依赖逐路径代理，漏配即整页空白", "后台-UI", "建议", "P3", "设计-可维护性", "新建",
     "阶段四（UI 冒烟）", "MALL-UI-005 / MALL-UI-007",
     "web 由 nginx 提供，接口走同源反向代理",
     "1. nginx 仅代理 /admin/ 前缀（mall-admin 的登录路径）\n"
     "2. 访问商品列表 /#/pms/product 与订单列表 /#/oms/order\n"
     "3. 观察页面与 nginx 访问日志",
     "商品/订单页整页空白；nginx 日志中没有任何 /product/list、/order/list 的代理记录，"
     "请求被 SPA 的 try_files 回落成 index.html，前端拿到 HTML 后 JSON 解析失败、未捕获 Promise 异常",
     "前端统一以 /api 作为接口前缀（或由网关按服务名路由），新增业务前缀无需修改代理配置",
     "环境迁移/网关变更时极易漏配导致功能整块不可用；本次已实际踩中，排查耗时约 40 分钟",
     "前端 axios baseURL 直接用空串或 /，业务接口路径各自为政（/admin、/product、/order、/role ...），"
     "反向代理必须穷举前缀",
     "统一 /api 前缀（本次已改为 VITE_BASE_SERVER_URL=/api 并在 nginx 做 rewrite）；"
     "或在网关统一路由，前端不再感知服务划分",
     "pytest tests/ui/test_ui_smoke.py::test_product_list tests/ui/test_ui_smoke.py::test_order_list -rs",
     "复现证据 E-U02"),
]

EVIDENCE = [
    ("E-06", "D-06", "POST /order/generateConfirmOrder",
     'body: [148]（cartIds）',
     'HTTP 500\n{"code":401,"message":"暂未登录或token已经过期","data":"Full authentication is required to access this resource"}',
     "docker logs mall-portal --tail 200 | findstr NullPointerException\n"
     "→ CartPromotionItem.getPrice() is null @ OmsPortalOrderServiceImpl.calcCartAmount:759",
     "响应被 /error 包装，真实异常需从容器日志取"),
    ("E-09", "D-09", "POST /order/cancelUserOrder?orderId=77（已支付）",
     "无 body，Header: Authorization: Bearer <会员token>",
     '{"code":200,"message":"操作成功"}',
     "SELECT status, pay_amount, payment_time FROM oms_order WHERE id=77;\n→ status=4，无退款记录",
     "支付后仍可取消，状态直接跳到已关闭"),
    ("E-10", "D-10", "POST /order/cancelUserOrder?orderId=92（B 取消 A 的订单）",
     "Header: Authorization: Bearer <B 的 token>",
     '{"code":200,"message":"操作成功"}\n（orderId=99999999 同样返回 200）',
     "SELECT id, member_id, status FROM oms_order WHERE id=92;\n→ member_id=A，status=4",
     "越权取消成功"),
    ("E-11", "D-11", "GET /order/detail/92（B 查询 A 的订单）",
     "Header: Authorization: Bearer <B 的 token>",
     '{"code":200,"data":{"id":92,"orderSn":"202611030100000016","receiverName":"自动化",...}}',
     "对照 SELECT member_id FROM oms_order WHERE id=92; → A",
     "越权读取成功"),
    ("E-14", "D-14", "POST /order/generateOrder",
     '{"memberReceiveAddressId":49,"couponId":null,"useIntegration":0,"payType":0,"cartIds":[]}',
     'HTTP 500\n{"code":500,"message":"You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version for the right syntax to use near \'\' at line 6","data":null}',
     "SELECT count(*) FROM oms_order WHERE member_id=<当前会员>;\n→ 未新增订单（失败）",
     "SQL 语法错误原文泄露"),
    ("E-15", "D-15", "POST /admin/register",
     '{"username":"sec_9527","password":"Test@1234","nickName":"sec"}（未带 token）',
     '{"code":200,"message":"操作成功"}\n随后 POST /admin/login 同账号 → code=200 拿到 token',
     "SELECT id, username, status FROM ums_admin WHERE username='sec_9527';",
     "未鉴权注册成功"),
    ("E-01", "D-01", "GET /sso/getAuthCode?telephone=13700000001",
     "无",
     '{"code":200,"message":"获取验证码成功","data":"355860"}',
     "docker exec mall-redis redis-cli -a mall123 GET ums:authCode:13700000001\n→ 与响应 data 一致（TTL 90s）",
     "验证码明文返回"),
    ("E-02", "D-02", "GET /product/detail/999999",
     "无",
     'HTTP 500\n{"code":401,"message":"暂未登录或token已经过期","data":"Full authentication is required to access this resource"}',
     "docker logs mall-portal | findstr /C:\"商品不存在\" /C:\"Exception\"",
     "真实异常被 401 掩盖"),
    ("E-13", "D-13", "POST /order/generateConfirmOrder",
     'body: [] 与 body: [99999999]',
     '两次均 {"code":200,"message":"操作成功","data":{"cartPromotionItemList":[],"calcAmount":{...}}}',
     "—",
     "空/无效购物车返回“成功”"),
    ("E-05", "D-05", "POST /admin/login（两次对比）",
     '{"username":"admin","password":"Wrong@123456"}\n{"username":"not_exist_9527","password":"Wrong@123456"}',
     '存在账号：{"code":500,"message":"密码不正确"}\n不存在：{"code":404,"message":"用户名或密码错误"}',
     "SELECT username FROM ums_admin WHERE username='admin';",
     "提示不一致可枚举"),
    ("E-16", "D-16", "POST /admin/login 连续 6 次",
     'body 固定 {"username":"admin","password":"Wrong@123"}',
     "6 次均返回业务失败；第 7 次正确密码直接登录成功，无锁定/验证码",
     "—",
     "无爆破防护"),
    ("E-07", "D-07", "POST /member/address/add",
     '缺必填：{"province":"广东省","city":"深圳市","region":"南山区","detailAddress":"x"}\n非法手机号：{"name":"A","phoneNumber":"abc123",...}',
     '两次均 {"code":200}',
     "SELECT id, name, phone_number FROM ums_member_receive_address WHERE member_id=<当前会员> ORDER BY id DESC;",
     "脏数据入库"),
    ("E-08", "D-08", "POST /member/address/add（第二次默认地址）",
     '{"name":"自动化测试","defaultStatus":1,...}',
     '{"code":200}',
     "SELECT id, default_status FROM ums_member_receive_address WHERE member_id=<当前会员>;\n→ 两条 default_status=1（id 45、46）",
     "默认地址不唯一"),
    ("E-12", "D-12", "POST /order/deleteOrder?orderId=90 → GET /order/detail/90",
     "Header: Authorization: Bearer <会员token>",
     '删除：{"code":200}\n详情：{"code":200,"data":{"id":90,...}}',
     "SELECT id, status, delete_status FROM oms_order WHERE id=90;\n→ delete_status=1，但详情仍返回",
     "软删除未生效于查询"),
    ("E-03", "D-03", "POST /admin/login",
     '{"username":"","password":"macro123"}',
     '{"code":404,"message":"username must not be empty"}',
     "—",
     "英文校验提示"),
    ("E-04", "D-04", "GET /admin/list（无 token）",
     "无 Authorization",
     'HTTP 200\n{"code":401,"message":"暂未登录或token已经过期"}',
     "对比 D-02 同类 401 却是 HTTP 500",
     "HTTP 状态码不统一"),
    ("E-17", "D-17", "GET /admin/login（带 Origin）",
     "Header: Origin: https://evil.example.com",
     "响应头 Access-Control-Allow-Origin: https://evil.example.com\nAccess-Control-Allow-Credentials: true",
     "—",
     "任意来源放行"),

    ("E-U01", "U-01", "GET /#/pms/product/index（浏览器地址栏）",
     "已登录状态（localStorage 有 token）",
     "页面 <div id=\"app\"><div data-v-app=\"\"></div></div>，body 文本为空；控制台无 404 提示",
     "截图：reports/ui-evidence/test_unknown_route_fallback_*/screenshot.png；DOM：同目录 page.html",
     "白屏且无兜底"),
    ("E-U02", "U-02", "GET /#/pms/product（仅代理 /admin/ 时）",
     "浏览器自动请求 /product/list?pageNum=1&pageSize=10",
     "nginx 未代理 → 返回 index.html（200 text/html）；控制台 SEVERE：Uncaught (in promise)；表格 0 行",
     "docker exec mall-admin-web grep '/product/list' /var/log/nginx/mall-web.access.log → 无记录",
     "整页空白，属环境配置缺口"),
]


def build_summary(wb, defects):
    ws = wb.create_sheet("缺陷统计")
    ws.sheet_properties.tabColor = "C00000"
    n = 6
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n)
    t = ws.cell(row=1, column=1, value="mall 商城 · 缺陷报告（V1.1）")
    t.font = F_TITLE
    t.fill = FILL_TITLE
    t.alignment = ALIGN_C
    ws.row_dimensions[1].height = 36

    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=n)
    sub = ws.cell(row=2, column=1, value=(
        f"被测版本：mall Spring Boot 3.5.14 ｜ 测试阶段：阶段二接口 + 阶段三全链路/安全 ｜ "
        f"缺陷总数 {len(defects)} 条 ｜ 报告日期 2026-11-03"))
    sub.font = Font(name="微软雅黑", size=9, color="404040")
    sub.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[2].height = 24

    by_sev = Counter(d[3] for d in defects)
    by_mod = Counter(d[2] for d in defects)
    by_stat = Counter(d[6] for d in defects)

    r = 4
    ws.cell(row=r, column=1, value="按严重程度").font = F_SECTION
    r += 1
    for h, idx, w in (("严重程度", 1, 14), ("数量", 2, 10), ("占比", 3, 10)):
        ws.cell(row=r, column=idx, value=h)
        ws.cell(row=r, column=idx).font = F_HEAD
        ws.cell(row=r, column=idx).fill = FILL_HEAD
        ws.cell(row=r, column=idx).alignment = ALIGN_C
    r += 1
    for sev in ("阻断", "严重", "主要", "次要", "建议"):
        cnt = by_sev.get(sev, 0)
        if not cnt:
            continue
        ws.cell(row=r, column=1, value=sev)
        ws.cell(row=r, column=2, value=cnt)
        ws.cell(row=r, column=3, value=f"{cnt / len(defects) * 100:.0f}%")
        fill, font = SEV_FILL.get(sev, (None, F_BODY))
        ws.cell(row=r, column=1).fill = fill
        ws.cell(row=r, column=1).font = font
        for c in range(1, 4):
            ws.cell(row=r, column=c).border = BORDER
            ws.cell(row=r, column=c).alignment = ALIGN_C
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="按模块").font = F_SECTION
    r += 1
    for h, idx in (("模块", 1), ("数量", 2), ("占比", 3)):
        ws.cell(row=r, column=idx, value=h).font = F_HEAD
        ws.cell(row=r, column=idx).fill = FILL_HEAD
        ws.cell(row=r, column=idx).alignment = ALIGN_C
    r += 1
    for mod, cnt in by_mod.most_common():
        ws.cell(row=r, column=1, value=mod)
        ws.cell(row=r, column=2, value=cnt)
        ws.cell(row=r, column=3, value=f"{cnt / len(defects) * 100:.0f}%")
        for c in range(1, 4):
            ws.cell(row=r, column=c).border = BORDER
            ws.cell(row=r, column=c).alignment = ALIGN_C
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="按状态").font = F_SECTION
    r += 1
    for h, idx in (("状态", 1), ("数量", 2)):
        ws.cell(row=r, column=idx, value=h).font = F_HEAD
        ws.cell(row=r, column=idx).fill = FILL_HEAD
        ws.cell(row=r, column=idx).alignment = ALIGN_C
    r += 1
    for stat, cnt in by_stat.items():
        ws.cell(row=r, column=1, value=stat)
        ws.cell(row=r, column=2, value=cnt)
        for c in range(1, 3):
            ws.cell(row=r, column=c).border = BORDER
            ws.cell(row=r, column=c).alignment = ALIGN_C
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="发布建议").font = F_SECTION
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r + 3, end_column=n)
    note = ws.cell(row=r, column=1, value=(
        "不建议上线：存在 6 条阻断级缺陷（下单主流程 NPE、已支付订单可取消、订单越权 2 处、SQL 报错泄露、"
        "后台注册未鉴权）。\n放行条件：6 条阻断全部修复且关联用例由 xfail 转 PASS；P0 用例 100% 通过；"
        "P1 用例通过率 ≥ 95%；回归 pytest -m smoke 与 pytest -m security 全绿。"))
    note.font = F_BODY
    note.alignment = ALIGN_L

    for i, w in enumerate([30, 12, 12, 12, 12, 12], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    return ws


def build_detail(wb, defects):
    ws = wb.create_sheet("缺陷明细")
    ws.sheet_properties.tabColor = "B23A3A"
    headers = ["缺陷编号", "缺陷标题", "所属模块", "严重程度", "优先级", "缺陷类型", "状态",
               "发现阶段", "关联用例", "前置条件", "复现步骤", "实际结果", "预期结果",
               "业务影响", "根因分析", "修复建议", "复现命令", "证据"]
    widths = [9, 34, 16, 9, 7, 15, 8, 13, 22, 26, 52, 52, 40, 36, 46, 46, 34, 16]
    n = len(headers)

    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n)
    t = ws.cell(row=1, column=1, value="缺陷明细（每条均可按「复现步骤」独立复现）")
    t.font = F_TITLE
    t.fill = FILL_TITLE
    t.alignment = ALIGN_C
    ws.row_dimensions[1].height = 32

    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=n)
    sub = ws.cell(row=2, column=1, value=f"测试环境：{ENV}")
    sub.font = Font(name="微软雅黑", size=9, color="404040")
    sub.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[2].height = 22

    for i, h in enumerate(headers, start=1):
        ws.cell(row=3, column=i, value=h)
        ws.cell(row=3, column=i).font = F_HEAD
        ws.cell(row=3, column=i).fill = FILL_HEAD
        ws.cell(row=3, column=i).alignment = ALIGN_C
        ws.cell(row=3, column=i).border = BORDER
    ws.row_dimensions[3].height = 30

    for r, d in enumerate(defects, start=4):
        for c, v in enumerate(d, start=1):
            cell = ws.cell(row=r, column=c, value=v)
            cell.font = F_MONO if c in (11, 12, 17) else F_BODY
            cell.border = BORDER
            cell.alignment = ALIGN_L if c in (2, 9, 10, 11, 12, 13, 14, 15, 16, 17) else ALIGN_C
            if r % 2 == 0:
                cell.fill = FILL_ZEBRA
        fill, font = SEV_FILL.get(d[3], (None, F_BODY))
        if fill:
            ws.cell(row=r, column=4).fill = fill
            ws.cell(row=r, column=4).font = font
        ws.row_dimensions[r].height = 190

    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    last = 3 + len(defects)
    ws.freeze_panes = "C4"
    ws.auto_filter.ref = f"A3:{get_column_letter(n)}{last}"

    dv_stat = DataValidation(type="list", allow_blank=True,
                             formula1='"新建,已确认,修复中,待验证,已关闭,拒绝,挂起"')
    ws.add_data_validation(dv_stat)
    dv_stat.add(f"G4:G{last + 100}")
    return ws


def build_evidence(wb):
    ws = wb.create_sheet("复现证据")
    ws.sheet_properties.tabColor = "ED7D31"
    headers = ["证据编号", "缺陷编号", "请求", "请求参数/头", "实际响应", "数据库/日志校验", "说明"]
    widths = [10, 10, 34, 44, 62, 52, 32]
    for i, h in enumerate(headers, start=1):
        ws.cell(row=1, column=i, value=h)
        ws.cell(row=1, column=i).font = F_HEAD
        ws.cell(row=1, column=i).fill = FILL_HEAD
        ws.cell(row=1, column=i).alignment = ALIGN_C
        ws.cell(row=1, column=i).border = BORDER
    ws.row_dimensions[1].height = 28

    for r, row in enumerate(EVIDENCE, start=2):
        for c, v in enumerate(row, start=1):
            cell = ws.cell(row=r, column=c, value=v)
            cell.font = F_MONO
            cell.border = BORDER
            cell.alignment = ALIGN_L
        ws.row_dimensions[r].height = 86
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    return ws


def build_spec(wb):
    ws = wb.create_sheet("报告规范")
    ws.sheet_properties.tabColor = "7F7F7F"
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 30
    ws.column_dimensions["C"].width = 86

    ws.merge_cells("A1:C1")
    t = ws["A1"]
    t.value = "缺陷报告规范（提交 / 定级 / 关闭）"
    t.font = F_TITLE
    t.fill = FILL_TITLE
    t.alignment = ALIGN_C
    ws.row_dimensions[1].height = 32

    rows = [
        ("SECTION", "一、生命周期"),
        ("新建", "测试提交缺陷", "必须填写：复现步骤、实际结果、预期结果、证据、关联用例"),
        ("已确认", "开发确认可复现", "开发需补充根因初步判断；无法复现需注明环境/数据差异"),
        ("修复中", "进入修复", "填写预计修复版本与时间"),
        ("待验证", "提交测试验证", "开发必须说明修改点，测试按原步骤 + 回归用例验证"),
        ("已关闭", "验证通过", "关联用例由 xfail 转 PASS，且 pytest -m regression 全绿"),
        ("拒绝 / 挂起", "非缺陷或暂不修复", "必须写理由与决策人；挂起需给复审时间"),

        ("SECTION", "二、严重程度定义"),
        ("阻断", "主流程不可用 / 资金或数据风险 / 严重越权", "版本不可发布，必须当天修复（如 D-06/D-09/D-10/D-11/D-14/D-15）"),
        ("严重", "核心功能出错但有绕行方案 / 信息泄露", "本迭代内修复"),
        ("主要", "非核心功能错误 / 校验缺失 / 防护不足", "按计划修复，可延至下个迭代"),
        ("次要", "体验、文案、配置类问题", "择机修复"),
        ("建议", "优化建议，非缺陷", "产品评估后决定"),

        ("SECTION", "三、必须提供的证据"),
        ("请求/响应", "完整报文（含 Header 关键项）", "禁止只贴一句“报错了”；需可对照接口契约"),
        ("失败信息", "断言信息或异常堆栈", "自动化用例直接贴 pytest 失败输出；手工测试贴日志"),
        ("数据佐证", "DB 查询结果 / Redis 值", "用于证明“数据被改/未被改”，如 select status from oms_order where id=? "),
        ("截图", "UI 类缺陷必附", "全屏 + 关键区域；命名 DEFECTID_步骤号.png"),
        ("环境信息", "版本、地址、账号、数据", "缺环境信息导致无法复现的缺陷，开发有权退回"),

        ("SECTION", "四、复现步骤写法"),
        ("可执行", "带具体 URL / 请求体 / 账号 / 数据前置", "把 reviewer 当成完全不了解系统的人"),
        ("可观察", "每一步都有可验证的中间结果", "如“第 3 步 GET /cart/list 应返回 1 条”"),
        ("最小化", "去掉与缺陷无关的操作", "能 3 步复现就不要 10 步"),
        ("定量", "给出具体数值/订单号/ID", "“某个订单”无法复现，“orderId=92”可以"),

        ("SECTION", "五、本报告的使用方式"),
        ("缺陷明细页", "按严重程度筛选", "冻结首列，支持按模块/状态过滤"),
        ("复现证据页", "每条缺陷对应的原始报文", "与缺陷明细的「证据」列一一对应（E-xx）"),
        ("与自动化打通", "关联用例列", "用例当前为 xfail，缺陷修复后自动转 PASS"),
        ("回归命令", "复现命令列", "直接复制执行，如 pytest tests/...::test_xxx -rs"),
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
        else:
            for c, val in enumerate(row, start=1):
                cell = ws.cell(row=r, column=c, value=val)
                cell.font = F_BODY
                cell.border = BORDER
                cell.alignment = ALIGN_L
            ws.cell(row=r, column=1).font = Font(name="微软雅黑", size=9, bold=True)
            ws.row_dimensions[r].height = 30
        r += 1
    return ws


def main():
    defects = DEFECTS
    wb = Workbook()
    wb.remove(wb.active)
    build_summary(wb, defects)
    build_detail(wb, defects)
    build_evidence(wb)
    build_spec(wb)
    wb.active = 1
    wb.save(OUT)
    print(f"saved: {OUT}")
    print(f"defects={len(defects)} evidence={len(EVIDENCE)}")
    print("severity:", dict(Counter(d[3] for d in defects)))


if __name__ == "__main__":
    main()
