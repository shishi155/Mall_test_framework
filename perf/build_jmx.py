# -*- coding: utf-8 -*-
"""生成 JMeter 测试计划（.jmx）。

设计：
- 5 个场景：后台登录 / 首页 / 搜索 / 商品详情 / 下单链路（登录→清车→加购→列表→确认单）
- 并发与时长全部用 -J 参数控制（threads/ramp/duration），一个脚本可跑基线/压力
- 断言响应体 "code":200（mall 的业务码在 body 里，HTTP 恒为 200）
- 下单场景刻意只到「确认单」，不真正 generateOrder，避免压测产生海量订单

用法: python perf/build_jmx.py
输出: perf/jmx/*.jmx
"""
from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

BASE = Path(__file__).resolve().parent
OUT = BASE / "jmx"
OUT.mkdir(parents=True, exist_ok=True)

HOST_PROP = "${__P(host,localhost)}"
THREADS = "${__P(threads,10)}"
RAMP = "${__P(ramp,10)}"
DURATION = "${__P(duration,60)}"


def header_xml(name: str, headers: dict) -> str:
    items = "".join(
        f"""        <elementProp name="" elementType="Header">
          <stringProp name="Header.name">{escape(k)}</stringProp>
          <stringProp name="Header.value">{escape(v)}</stringProp>
        </elementProp>
""" for k, v in headers.items())
    return f"""      <HeaderManager guiclass="HeaderPanel" testclass="HeaderManager" testname="{name}" enabled="true">
        <collectionProp name="HeaderManager.headers">
{items}        </collectionProp>
      </HeaderManager>
      <hashTree/>
"""


def json_body_sampler(name: str, path: str, method: str, body: str | None = None,
                      params: dict | None = None, extra_headers: dict | None = None) -> str:
    """构造 HTTP 采样器；body 为原始 JSON，params 为表单/查询参数。"""
    args = []
    if body is not None:
        args.append(f"""            <elementProp name="" elementType="HTTPArgument">
              <boolProp name="HTTPArgument.always_encode">false</boolProp>
              <stringProp name="Argument.value">{escape(body)}</stringProp>
              <stringProp name="Argument.metadata">=</stringProp>
            </elementProp>
""")
    for k, v in (params or {}).items():
        args.append(f"""            <elementProp name="{escape(k)}" elementType="HTTPArgument">
              <boolProp name="HTTPArgument.always_encode">true</boolProp>
              <stringProp name="Argument.name">{escape(k)}</stringProp>
              <stringProp name="Argument.value">{escape(str(v))}</stringProp>
              <stringProp name="Argument.metadata">=</stringProp>
              <boolProp name="HTTPArgument.use_equals">true</boolProp>
            </elementProp>
""")
    args_xml = "".join(args)
    post_raw = "true" if body is not None else "false"
    method_xml = f"""        <stringProp name="HTTPSampler.method">{method}</stringProp>
        <stringProp name="HTTPSampler.path">{escape(path)}</stringProp>
        <boolProp name="HTTPSampler.follow_redirects">true</boolProp>
        <boolProp name="HTTPSampler.auto_redirects">false</boolProp>
        <boolProp name="HTTPSampler.use_keepalive">true</boolProp>
        <boolProp name="HTTPSampler.postBodyRaw">{post_raw}</boolProp>
"""
    headers = ""
    if extra_headers:
        headers = header_xml(f"{name} 请求头", extra_headers)

    return f"""        <HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" testname="{escape(name)}" enabled="true">
          <elementProp name="HTTPsampler.Arguments" elementType="Arguments" guiclass="HTTPArgumentsPanel" testclass="Arguments" enabled="true">
            <collectionProp name="Arguments.arguments">
{args_xml}            </collectionProp>
          </elementProp>
{method_xml}        </HTTPSamplerProxy>
        <hashTree>
{headers}          <ResponseAssertion guiclass="AssertionGui" testclass="ResponseAssertion" testname="断言 code=200" enabled="true">
            <collectionProp name="Asserion.test_strings">
              <stringProp name="49586">&quot;code&quot;:200</stringProp>
            </collectionProp>
            <stringProp name="Assertion.custom_message">业务码非 200</stringProp>
            <stringProp name="Assertion.test_field">Assertion.response_data</stringProp>
            <boolProp name="Assertion.assume_success">false</boolProp>
            <intProp name="Assertion.test_type">16</intProp>
          </ResponseAssertion>
          <hashTree/>
        </hashTree>
"""


def extractor(step_name: str, ref: str, expr: str) -> str:
    return f"""          <JSONPostProcessor guiclass="JSONPostProcessorGui" testclass="JSONPostProcessor" testname="提取 {ref}" enabled="true">
            <stringProp name="JSONPostProcessor.referenceNames">{ref}</stringProp>
            <stringProp name="JSONPostProcessor.jsonPathExprs">{escape(expr)}</stringProp>
            <stringProp name="JSONPostProcessor.match_numbers">1</stringProp>
            <stringProp name="JSONPostProcessor.defaultValues">NOT_FOUND</stringProp>
          </JSONPostProcessor>
          <hashTree/>
"""


def plan(name: str, port: int, steps: str, csv: str | None = None) -> str:
    csv_xml = ""
    if csv:
        csv_xml = f"""      <CSVDataSet guiclass="TestBeanGUI" testclass="CSVDataSet" testname="CSV 数据" enabled="true">
        <stringProp name="filename">{escape(str(BASE / 'data' / csv))}</stringProp>
        <stringProp name="fileEncoding">UTF-8</stringProp>
        <stringProp name="variableNames">username,password,productId,skuId</stringProp>
        <boolProp name="ignoreFirstLine">true</boolProp>
        <stringProp name="delimiter">,</stringProp>
        <boolProp name="quotedData">false</boolProp>
        <boolProp name="recycle">true</boolProp>
        <boolProp name="stopThread">false</boolProp>
        <stringProp name="shareMode">shareMode.all</stringProp>
      </CSVDataSet>
      <hashTree/>
"""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6.3">
  <hashTree>
    <TestPlan guiclass="TestPlanGui" testclass="TestPlan" testname="{escape(name)}" enabled="true">
      <stringProp name="TestPlan.comments">mall 性能测试 · 参数化：-Jhost -Jport -Jthreads -Jramp -Jduration</stringProp>
      <boolProp name="TestPlan.functional_mode">false</boolProp>
      <boolProp name="TestPlan.tearDown_on_shutdown">true</boolProp>
      <boolProp name="TestPlan.serialize_threadgroups">false</boolProp>
      <elementProp name="TestPlan.user_defined_variables" elementType="Arguments" guiclass="ArgumentsPanel" testclass="Arguments" testname="User Defined Variables" enabled="true">
        <collectionProp name="Arguments.arguments"/>
      </elementProp>
      <stringProp name="TestPlan.user_define_classpath"></stringProp>
    </TestPlan>
    <hashTree>
      <ConfigTestElement guiclass="HttpDefaultsGui" testclass="ConfigTestElement" testname="HTTP 请求默认" enabled="true">
        <elementProp name="HTTPsampler.Arguments" elementType="Arguments" guiclass="HTTPArgumentsPanel" testclass="Arguments" testname="用户定义的变量" enabled="true">
          <collectionProp name="Arguments.arguments"/>
        </elementProp>
        <stringProp name="HTTPSampler.domain">{HOST_PROP}</stringProp>
        <stringProp name="HTTPSampler.port">${{__P(port,{port})}}</stringProp>
        <stringProp name="HTTPSampler.protocol">http</stringProp>
        <stringProp name="HTTPSampler.contentEncoding">UTF-8</stringProp>
        <stringProp name="HTTPSampler.connect_timeout">5000</stringProp>
        <stringProp name="HTTPSampler.response_timeout">20000</stringProp>
      </ConfigTestElement>
      <hashTree/>
      <HeaderManager guiclass="HeaderPanel" testclass="HeaderManager" testname="公共请求头" enabled="true">
        <collectionProp name="HeaderManager.headers">
          <elementProp name="" elementType="Header">
            <stringProp name="Header.name">Content-Type</stringProp>
            <stringProp name="Header.value">application/json</stringProp>
          </elementProp>
        </collectionProp>
      </HeaderManager>
      <hashTree/>
{csv_xml}      <ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" testname="并发线程组" enabled="true">
        <stringProp name="ThreadGroup.on_sample_error">continue</stringProp>
        <elementProp name="ThreadGroup.main_controller" elementType="LoopController" guiclass="LoopControlPanel" testclass="LoopController" testname="循环控制器" enabled="true">
          <boolProp name="LoopController.continue_forever">false</boolProp>
          <stringProp name="LoopController.loops">-1</stringProp>
        </elementProp>
        <stringProp name="ThreadGroup.num_threads">{THREADS}</stringProp>
        <stringProp name="ThreadGroup.ramp_time">{RAMP}</stringProp>
        <boolProp name="ThreadGroup.scheduler">true</boolProp>
        <stringProp name="ThreadGroup.duration">{DURATION}</stringProp>
        <stringProp name="ThreadGroup.delay">0</stringProp>
        <boolProp name="ThreadGroup.same_user_on_next_iteration">true</boolProp>
      </ThreadGroup>
      <hashTree>
{steps}      </hashTree>
    </hashTree>
  </hashTree>
</jmeterTestPlan>
"""


def build():
    # 01 后台登录
    login_admin = json_body_sampler(
        "POST /admin/login", "/admin/login", "POST",
        body='{"username":"admin","password":"macro123"}',
    )
    (OUT / "01-admin-login.jmx").write_text(
        plan("01 后台登录", 8080, login_admin), encoding="utf-8")

    # 02 首页
    home = json_body_sampler("GET /home/content", "/home/content", "GET")
    (OUT / "02-portal-home.jmx").write_text(
        plan("02 前台首页", 8085, home), encoding="utf-8")

    # 03 搜索
    search = json_body_sampler(
        "GET /product/search", "/product/search", "GET",
        params={"keyword": "手机", "pageNum": 1, "pageSize": 5},
    )
    (OUT / "03-portal-search.jmx").write_text(
        plan("03 前台搜索", 8085, search), encoding="utf-8")

    # 04 商品详情
    detail = json_body_sampler(
        "GET /product/detail/27", "/product/detail/${__P(productId,27)}", "GET")
    (OUT / "04-portal-product-detail.jmx").write_text(
        plan("04 商品详情", 8085, detail), encoding="utf-8")

    # 05 下单链路：登录 → 清车 → 加购 → 列表 → 确认单
    steps = []
    steps.append(json_body_sampler(
        "1. 会员登录", "/sso/login", "POST",
        params={"username": "perf${__threadNum}", "password": "Perf@1234"},
        # /sso/login 用 @RequestParam 接收，必须表单提交而非 JSON
        extra_headers={"Content-Type": "application/x-www-form-urlencoded"},
    ).replace(
        """          <ResponseAssertion guiclass="AssertionGui\"""",
        """          <JSONPostProcessor guiclass="JSONPostProcessorGui" testclass="JSONPostProcessor" testname="提取 token" enabled="true">
            <stringProp name="JSONPostProcessor.referenceNames">token</stringProp>
            <stringProp name="JSONPostProcessor.jsonPathExprs">$.data.token</stringProp>
            <stringProp name="JSONPostProcessor.match_numbers">1</stringProp>
            <stringProp name="JSONPostProcessor.defaultValues">NOT_FOUND</stringProp>
          </JSONPostProcessor>
          <hashTree/>
          <ResponseAssertion guiclass="AssertionGui\"""",
        1,
    ))
    steps.append(json_body_sampler(
        "2. 清空购物车", "/cart/clear", "POST",
        extra_headers={"Authorization": "Bearer ${token}"},
    ))
    steps.append(json_body_sampler(
        "3. 加入购物车", "/cart/add", "POST",
        body='{"productId":${__P(productId,26)},"productSkuId":${__P(skuId,110)},"quantity":1}',
        extra_headers={"Authorization": "Bearer ${token}"},
    ))
    list_step = json_body_sampler(
        "4. 购物车列表", "/cart/list", "GET",
        extra_headers={"Authorization": "Bearer ${token}"},
    ).replace(
        """          <ResponseAssertion guiclass="AssertionGui\"""",
        """          <JSONPostProcessor guiclass="JSONPostProcessorGui" testclass="JSONPostProcessor" testname="提取 cartId" enabled="true">
            <stringProp name="JSONPostProcessor.referenceNames">cartId</stringProp>
            <stringProp name="JSONPostProcessor.jsonPathExprs">$.data[0].id</stringProp>
            <stringProp name="JSONPostProcessor.match_numbers">1</stringProp>
            <stringProp name="JSONPostProcessor.defaultValues">NOT_FOUND</stringProp>
          </JSONPostProcessor>
          <hashTree/>
          <ResponseAssertion guiclass="AssertionGui\"""",
        1,
    )
    steps.append(list_step)
    steps.append(json_body_sampler(
        "5. 生成确认单", "/order/generateConfirmOrder", "POST",
        body="[${cartId}]",
        extra_headers={"Authorization": "Bearer ${token}"},
    ))
    (OUT / "05-portal-order-flow.jmx").write_text(
        plan("05 下单链路（到确认单）", 8085, "".join(steps)),
        encoding="utf-8")

    for f in sorted(OUT.glob("*.jmx")):
        print(f"generated: {f.relative_to(BASE.parent)} ({f.stat().st_size} bytes)")


if __name__ == "__main__":
    build()
