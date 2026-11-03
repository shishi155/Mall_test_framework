# mall 商城 —— 全栈测试工程

> 被测系统：`mall`（Spring Boot 3.5.14 + JDK 17 + MySQL/Redis/MongoDB/RabbitMQ/Elasticsearch）
> 前端：`mall-admin-web`（Vue 3 + Vite + Element Plus）
> 测试目标：**以接口测试为主**，配合后台 UI 冒烟、性能压测、安全测试，Jenkins 容器化 CI/CD

---

## 一、测试策略总览

| 测试类型 | 工具/框架 | 覆盖重点 | 状态 |
|---|---|---|---|
| 环境管理 | Docker Compose | 一键起停被测系统全栈 | ✅ 阶段一完成 |
| 接口/功能测试 | **pytest + requests + Allure** | portal 全业务链路 + admin 核心 P0 | ⏳ 阶段二/三 |
| UI 冒烟 | **Selenium 4 + POM** | 后台管理端登录、商品、订单等少量主流程 | ⏳ 阶段四 |
| 性能测试 | **JMeter 5.6.3** | 登录/首页/搜索/详情/下单链路 5 个场景，基线与 50 并发压力 | ✅ 阶段五完成 |
| 安全测试 | OWASP ZAP + 手写安全用例 | SQL 注入、XSS、越权(IDOR)、JWT、未授权访问 | ⏳ 阶段六 |
| CI/CD | **Jenkins（容器化）** | 拉码→起环境→冒烟→回归→UI→定时性能→Allure 发布 | ⏳ 阶段七 |
| 文档建设 | Markdown + Allure + Excel | 计划/方案/用例/缺陷/报告/手册 | ⏳ 持续 |

**取舍原则**：接口为主（覆盖率高、执行快、易维护），UI 只做核心链路冒烟（维护成本高），
性能与安全按周期回归而非每次提交执行。

---

## 二、被测系统速览

| 模块 | 说明 | 端口 | Controller |
|---|---|---|---|
| mall-admin | 后台管理接口 | 18080 | 31 |
| mall-portal | 前台商城接口 | 8085 | 13 |
| mall-search | ES 商品搜索 | 18081 | 1 |
| mall-admin-web | 后台管理前端 | 8090 | — |

内置账号：`admin / macro123`（后台）、前台需先 `GET /sso/getAuthCode?telephone=xxx` 取验证码再注册。

---

## 三、目录约定

```
Mall_test/
├─ env/            # 环境编排：compose、Dockerfile、初始化 SQL、一键脚本
├─ docs/           # 测试文档（环境手册、框架手册、计划、方案、报告）
├─ config/         # ✅ 多环境配置 config.yaml + settings.py
├─ common/         # ✅ 请求封装、断言库、DB、数据工厂、Excel 读取、日志
├─ api/            # ✅ 接口对象层（admin/ portal/）+ Excel 驱动注册表 registry.py
├─ tests/          # ✅ 用例：admin / portal / excel
│  ├─ admin/       #   后台登录鉴权、商品
│  ├─ portal/      #   前台注册登录、商品、购物车
│  ├─ excel/       #   Excel 驱动的单接口校验点
│  ├─ ui/          #   Selenium 用例（阶段四）
│  └─ security/    #   安全用例（阶段六）
├─ testcases/      # ✅ 用例 Excel（V0.2）+ 生成脚本
├─ scripts/        # ✅ run-tests.cmd（跑用例 + 出 Allure 报告）
├─ data/           # yaml 数据池（按需）
├─ perf/           # ✅ JMeter 脚本生成、压测数据、结果汇总与报告生成
├─ jenkins/        # Jenkinsfile、compose、插件清单（阶段七）
├─ reports/        # allure-results / allure-report / logs
└─ build/          # 构建日志等中间产物（可清理）
```

---

## 四、快速开始

```powershell
cd env\scripts
.\pull-images.cmd      # 拉基础镜像（Docker Hub 不通时自动走国内源）
.\build-images.cmd     # 打包后端 + 构建 4 个镜像
.\env-up.cmd           # 启动全栈并等待就绪
.\env-status.cmd       # 巡检
```

访问：

- 后台前端：http://localhost:8090 （admin / macro123）
- 后台 Swagger：http://localhost:18080/swagger-ui.html
- 前台接口：http://localhost:8085
- RabbitMQ 控制台：http://localhost:15672 （mall / mall123）

详细说明见 [环境搭建手册](docs/01-环境搭建手册.md)。

---

## 四·二、执行测试

```powershell
cd C:\path\to\Mall_test

# 首次：创建虚拟环境并装依赖
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 跑用例
cd scripts
.\run-tests.cmd -m smoke          # 冒烟（19 条，约 4 秒）
.\run-tests.cmd                   # 全量（31 条通过 + 3 条已知缺陷 xfail）
.\run-tests.cmd -m smoke -allure  # 跑完生成 Allure 报告
```

框架用法见 [测试框架使用手册](docs/02-测试框架使用手册.md)，执行结果与缺陷分析见 [接口测试执行报告](docs/03-接口测试执行报告.md)，性能结论见 [性能测试报告](docs/04-性能测试报告.md)，CI 见 [CI/CD 手册](docs/05-CICD手册.md) 与 [定时任务与邮件通知](docs/06-定时任务与邮件通知.md)。

---

## 五、进度看板

- [x] **阶段一：环境容器化**
  - 全栈 compose（基础设施 5 + 后端 3 + 前端 1），健康检查与依赖顺序
  - 一键脚本（拉镜像 / 构建 / 起停 / 巡检 / 就绪等待）
  - 环境搭建手册（含端口冲突、镜像加速、编码陷阱等实测问题）
- [x] **阶段二：pytest + Allure 框架骨架 + 用例体系**
  - 分层：config / common / api / tests，接口对象层 + Excel 驱动注册表
  - 夹具：后台 token、运行时注册会员、DB 连接、可售商品（DB 动态选取）、购物车清理
  - 断言库：业务码 / message / data / 敏感信息泄露 / 接口与 DB 一致性
  - 用例工作簿 V0.2：6 个 sheet（说明 / 用例详情 19 条 / 参数化数据 12 条 / 测试数据 / 覆盖矩阵 / 缺陷线索）
  - 31 条自动化用例通过，3 条已知缺陷 xfail（D-01 验证码明文、D-02 异常路径 500+401、D-05 账号枚举）
  - Allure 报告可生成（含环境信息、请求/响应附件、case_id 标签）
- [x] **阶段三：接口用例补全（152 条，全链路 + 后台 P0 + 安全专项）**
  - 用例从 34 → **152**：后台 46 / 前台 76 / 跨端 30（安全 + Excel 驱动）
  - 新增业务域：收货地址、订单全链路（确认单→下单→支付→取消→删除）、会员中心（收藏/足迹/关注）、优惠券、首页品牌、后台商品/订单/角色权限/营销与基础数据、安全专项 16 条
  - 执行结果：**131 passed / 20 xfailed / 1 skipped**，耗时 28s，无 flaky
  - 用例工作簿 **V1.0**：138 条用例台账由源码自动收集（`testcases/collect_cases.py`），与 pytest 双向可追溯
  - 缺陷台账 **D-01 ~ D-17**，其中严重 6 条（下单 NPE、订单越权、SQL 泄露、后台注册未鉴权等）
  - 交付《接口测试执行报告》：分层统计、缺陷分析、发布建议（**不建议上线**）
- [x] **阶段四：Selenium 后台 UI 冒烟（11 条）**
  - Page Object + headless Chrome；每用例独立 profile，避免 token 串号
  - 失败自动采集 **截图 + DOM 快照 + 控制台日志**，落盘 `reports/ui-evidence/` 并挂 Allure
  - 覆盖登录/首页/商品/订单/权限/路由兜底；发现 U-01 未知路由白屏、U-02 接口无统一前缀（导致整页空白）
  - 同时修复环境侧问题：前端 API 统一 `/api` 前缀 + nginx rewrite
- [x] **阶段五：JMeter 性能测试（5 场景 + 基线/压力）**
  - 场景：后台登录、前台首页、搜索、商品详情、下单链路（到确认单）
  - 参数化：`-Jthreads/-Jramp/-Jduration`，每线程独立账号（`perf${__threadNum}`）避免购物车互相清空
  - 基线 10 并发：首页 584 TPS / 搜索 922 TPS / 详情 587 TPS / 登录 70 TPS（BCrypt 约 130ms）
  - 压力 50 并发：首页 629 TPS / 登录 82 TPS（RT 508ms，CPU 打满，扩展性差）
  - 输出：JMeter HTML 报告 + `reports/perf/summary.md` + 《04-性能测试报告》
- [ ] 阶段六：安全测试深化（ZAP 扫描）— 按用户要求暂缓
- [x] **阶段七：Jenkins 容器化 CI/CD**
  - Jenkins 2.541.3 + Selenium 4 容器，同 `mall-test_mall-net` 网络；测试在 Jenkins 容器内执行（无 DinD）
  - 流水线：环境检查 → 接口冒烟 → 接口全量 → UI 冒烟 → 性能基线（可选）→ Allure 归档
  - 实测：#1（smoke+UI）153.7s SUCCESS；#2（full+UI+perf 5 场景）496s SUCCESS；#3（full 接口）158.4s SUCCESS，全量 131 passed / 20 xfail
  - 交付《05-CICD手册》+ `jenkins/` 全套资产（Dockerfile/plugins/CasC/Jenkinsfile/建任务与触发脚本）
- [x] **阶段七补充：定时任务 + 邮件通知**
  - 3 个 Job：`mall-cicd`（手动）、`mall-cicd-daily`（工作日 09:00 全量+UI，成功发汇总）、`mall-cicd-nightly`（每日 02:00 全量+UI+性能，失败才发）
  - 定时触发器实测：自检任务按 `*/2 * * * *` 在 00:04:00 自动触发（原因 `Started by timer`）
  - 邮件：QQ/163 SMTP，失败必发、成功按 `NOTIFY_DAILY` 汇总；通知失败不影响构建
  - **Allure Jenkins 插件已集成**：构建页报告入口、项目级报告、跨构建趋势图（实测 2 次构建历史）
  - 已用本地模拟 SMTP 验证收信成功（含中文主题、HTML 正文、用例统计）
  - 交付《06-定时任务与邮件通知》
