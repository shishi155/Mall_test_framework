"""Excel 驱动的单接口校验点用例。

C 混合模式的「执行」这一半：Excel「参数化数据」sheet 一行 = 一次接口调用，
这里只做通用的执行 + 断言，新增用例只改 Excel，不改代码。
"""
from __future__ import annotations

from typing import Any, Dict, List

import allure
import pytest

from api.registry import REGISTRY
from common import assertions as A
from common.excel_loader import load_point_cases
from common.logger import get_logger
from config.settings import load_settings

log = get_logger("excel-driven")

_SETTINGS = load_settings()
_CASE_FILE = _SETTINGS.case_file

try:
    POINT_CASES: List[Dict[str, Any]] = load_point_cases(_CASE_FILE)
except FileNotFoundError:
    POINT_CASES = []
    log.warning("未找到用例文件 %s，Excel 驱动用例将被跳过", _CASE_FILE)

pytestmark = [pytest.mark.point, allure.epic("mall 商城"), allure.feature("单接口校验点（Excel 驱动）")]


def _ids(cases):
    return [c["case_id"] for c in cases]


@pytest.mark.parametrize("case", POINT_CASES, ids=_ids(POINT_CASES))
def test_point_case(case, ctx_factory):
    case_id = case["case_id"]
    api_key = case["api_key"]

    allure.dynamic.title(f"{case_id} {case.get('remark') or api_key}")
    allure.dynamic.label("case_id", case_id)
    allure.dynamic.description(
        f"接口: {case['method']} {case['path']}\n参数: {case['params']}\n"
        f"期望: code={case['expect_code']} message含={case['expect_message']!r}"
    )

    if api_key not in REGISTRY:
        pytest.skip(f"接口标识 {api_key} 尚未注册，请在 api/registry.py 中补充")

    ctx = ctx_factory(bool(case["with_token"]))
    with allure.step(f"{case['method']} {case['path']}"):
        resp = REGISTRY[api_key](ctx, case["params"])

    with allure.step(f"断言 code={case['expect_code']}"):
        A.assert_code(resp, case["expect_code"], case["expect_message"] or None)

    if case["expect_data"]:
        with allure.step("断言 data 非空"):
            A.assert_data_not_empty(resp)
