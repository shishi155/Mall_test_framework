"""用例 Excel 读取器（C 混合模式的「读」这一半）。

两处用途：
1. 用例详情 sheet —— 设计文档 + 追溯（人读，pytest 只读不写）；
2. 参数化数据 sheet —— 单接口校验点的机读数据，直接驱动 pytest 执行。

两者通过「用例编号」关联：Excel 里写清楚，代码里 @pytest.mark.case_id 对上。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from openpyxl import load_workbook

from common.logger import get_logger

log = get_logger("excel")

CASE_SHEET = "用例详情"
POINT_SHEET = "参数化数据"

# 用例详情：表头 -> 字段名（表头在第 3 行，数据从第 4 行开始）
CASE_HEADER_MAP = {
    "用例编号": "case_id",
    "所属端": "side",
    "模块": "module",
    "子模块": "sub_module",
    "用例标题": "title",
    "用例类型": "case_type",
    "设计方法": "design_method",
    "优先级": "priority",
    "前置条件": "precondition",
    "测试数据": "test_data",
    "操作步骤": "steps",
    "预期结果": "expected",
    "关联接口": "api",
    "自动化状态": "auto_status",
    "自动化用例ID": "auto_id",
    "最近执行结果": "last_result",
    "备注": "remark",
}

# 参数化数据：表头 -> 字段名（表头第 1 行）
POINT_HEADER_MAP = {
    "用例编号": "case_id",
    "接口标识": "api_key",
    "方法": "method",
    "路径": "path",
    "传参方式": "payload_kind",
    "参数(JSON)": "params",
    "携带token": "with_token",
    "期望code": "expect_code",
    "期望message包含": "expect_message",
    "期望data非空": "expect_data",
    "备注": "remark",
}


def _read_sheet(path: Path, sheet: str, header_row: int, mapping: Dict[str, str]) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"用例文件不存在：{path}")
    wb = load_workbook(path, data_only=True)
    if sheet not in wb.sheetnames:
        raise KeyError(f"工作表 {sheet} 不存在，现有：{wb.sheetnames}")
    ws = wb[sheet]

    header_cells = [c.value for c in ws[header_row]]
    col_index = {}
    for idx, title in enumerate(header_cells, start=1):
        if title and str(title).strip() in mapping:
            col_index[mapping[str(title).strip()]] = idx
    missing = set(mapping.values()) - set(col_index)
    if missing:
        log.warning("工作表 %s 缺少列：%s", sheet, missing)

    rows: List[Dict[str, Any]] = []
    for r in range(header_row + 1, ws.max_row + 1):
        record = {}
        for key, idx in col_index.items():
            v = ws.cell(row=r, column=idx).value
            record[key] = v.strip() if isinstance(v, str) else v
        if record.get("case_id"):
            rows.append(record)
    return rows


def load_cases(path: Path | str) -> List[Dict[str, Any]]:
    """读取用例详情（设计文档视角）。"""
    return _read_sheet(Path(path), CASE_SHEET, 3, CASE_HEADER_MAP)


def load_point_cases(path: Path | str) -> List[Dict[str, Any]]:
    """读取参数化数据，供 pytest 直接执行；参数列按 JSON 解析。"""
    raw = _read_sheet(Path(path), POINT_SHEET, 1, POINT_HEADER_MAP)
    cases = []
    for r in raw:
        params = r.get("params")
        if isinstance(params, str) and params.strip():
            try:
                r["params"] = json.loads(params)
            except json.JSONDecodeError as e:
                raise ValueError(f"用例 {r['case_id']} 的参数不是合法 JSON：{params}（{e}）") from e
        else:
            r["params"] = {}
        r["with_token"] = str(r.get("with_token") or "").strip().lower() in ("是", "true", "1", "y", "yes")
        r["expect_code"] = int(r["expect_code"]) if r.get("expect_code") not in (None, "") else 200
        r["expect_data"] = str(r.get("expect_data") or "").strip().lower() in ("是", "true", "1", "y", "yes")
        cases.append(r)
    return cases


def filter_cases(
    cases: Iterable[Dict[str, Any]],
    *,
    side: Optional[str] = None,
    module: Optional[str] = None,
    case_type: Optional[str] = None,
    priority: Optional[str] = None,
) -> List[Dict[str, Any]]:
    out = []
    for c in cases:
        if side and c.get("side") != side:
            continue
        if module and c.get("module") != module:
            continue
        if case_type and c.get("case_type") != case_type:
            continue
        if priority and c.get("priority") != priority:
            continue
        out.append(c)
    return out
