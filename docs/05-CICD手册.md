# 05 · CI/CD 手册（Jenkins 容器化）

> Jenkins 版本：2.541.3 LTS + JDK 17　访问地址：http://localhost:8081 （admin / admin123）
> 被测环境：mall-test 全栈（Docker Compose），Jenkins 与其同网络
> 流水线：环境检查 → 接口冒烟 → 接口全量 → UI 冒烟 → 性能基线（可选）→ 报告归档
> 工作目录：容器内 `/var/jenkins_home/mall`（挂载宿主机工程目录）

---

## 一、架构

```
┌───────────────────────────────────────────────┐
│ mall-jenkins (jenkins/jenkins:lts-jdk17 定制)  │
│  ├─ Python 3.13 + pytest + allure-pytest       │
│  ├─ JMeter 5.6.3（性能阶段）                    │
│  ├─ Allure CLI 2.30（生成 HTML 报告）           │
│  └─ 工作目录 /var/jenkins_home/mall ← 挂载工程目录 │
└───────────────┬───────────────────────────────┘
                │ docker 网络 mall-test_mall-net
    ┌───────────┼────────────┬─────────────┐
    ▼           ▼            ▼             ▼
mall-admin  mall-portal  mall-admin-web  mall-mysql / redis / es ...
                ▲
                │ WebDriver（remote）
        ┌───────┴────────┐
        │ mall-selenium  │ selenium/standalone-chrome
        └────────────────┘
```

**为什么测试用例跑在 Jenkins 容器里而不是再起一个 agent 容器**：
- 避免 docker-in-docker（Windows + WSL2 下 DinD 不稳定）；
- 依赖在镜像构建期装好，流水线无需联网装包，执行稳定；
- UI 用例通过 `SELENIUM_REMOTE_URL` 连独立浏览器容器，浏览器崩溃不会拖垮 Jenkins。

---

## 二、目录与文件

| 文件 | 作用 |
|---|---|
| `jenkins/Dockerfile` | CI 镜像：Jenkins + Python + JMeter + Allure + 测试依赖 + 插件 |
| `jenkins/plugins.txt` | 构建期安装的 Jenkins 插件（pipeline/git/timestamper/ws-cleanup/build-timeout/CasC/**allure-jenkins-plugin**） |
| `jenkins/casc.yaml` | Jenkins 初始化配置（admin 账号、关闭安装向导、时区、git 工具、**Allure 命令行指向 /opt/allure**） |
| `jenkins/docker-compose.jenkins.yml` | Jenkins + Selenium 编排，加入 `mall-test_mall-net` 网络 |
| `jenkins/Jenkinsfile` | 声明式流水线定义 |
| `jenkins/create_job.py` | 通过 REST API 创建/更新任务并触发构建、跟随日志 |
| `perf/run-perf.sh` | Linux 容器内的 JMeter 批量执行（Windows 用 `run-perf.ps1`） |

---

## 三、首次部署

```powershell
cd C:\path\to\Mall_test

# 1) 确保被测环境已启动（mall-test 网络存在）
cd env\scripts; .\env-up.cmd

# 2) 构建 CI 镜像并启动
cd ..\..\jenkins
docker compose -f docker-compose.jenkins.yml build
docker compose -f docker-compose.jenkins.yml up -d

# 3) 等待 Jenkins 就绪（首次约 40s），创建任务并触发第一次构建
cd ..
.\.venv\Scripts\python.exe jenkins\create_job.py
```

访问 http://localhost:8081 → 任务 `mall-cicd`，账号 `admin / admin123`。

---

## 四、流水线阶段

| 阶段 | 内容 | 耗时（实测） | 失败是否阻断 |
|---|---|---|---|
| 环境检查 | 打印版本、探活 mall-admin/portal/web、统计用例数 | ~5s | 是 |
| 接口冒烟 | `pytest -m smoke` | ~12s | 是 |
| 接口全量 | `pytest tests/admin tests/portal tests/security tests/excel`（SCOPE=full 时执行） | ~35s | 是 |
| UI 冒烟 | `pytest tests/ui`（远程 Selenium） | ~60s | 是 |
| 性能基线 | `perf/run-perf.sh` 5 场景 × 30s（RUN_PERF=true 时执行） | ~4min | 是 |
| 报告归档 | Allure HTML 生成 + `archiveArtifacts` | ~10s | 否 |

**参数**：

| 参数 | 可选值 | 说明 |
|---|---|---|
| `SCOPE` | smoke / full | 接口用例执行范围 |
| `RUN_UI` | true / false | 是否跑 UI 冒烟 |
| `RUN_PERF` | true / false | 是否跑性能基线（耗时最长，建议定时任务单独跑） |

---

## 四·二、定时任务与通知

- 三条流水线：`mall-cicd`（手动）、`mall-cicd-daily`（工作日 09:00 全量+UI）、`mall-cicd-nightly`（每日 02:00 含性能）；
- 邮件通知：失败必发，`NOTIFY_DAILY=true` 时成功也发（每日汇总）；
- 详见 [06-定时任务与邮件通知](06-定时任务与邮件通知.md)。

---

## 五、触发方式

**方式一：界面**　打开任务 → Build with Parameters → 选择参数 → 构建

**方式二：命令行（脚本）**

```powershell
.\.venv\Scripts\python.exe jenkins\create_job.py            # 建任务 + 触发 + 跟随日志
.\.venv\Scripts\python.exe jenkins\create_job.py --no-build # 只建/更新任务
.\.venv\Scripts\python.exe jenkins\create_job.py --watch    # 只跟随最近一次构建
```

**方式三：REST API**

```powershell
$auth = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes('admin:admin123'))
$h = @{ Authorization = "Basic $auth" }
$crumb = (Invoke-RestMethod 'http://localhost:8081/crumbIssuer/api/json' -Headers $h).crumb
$h['Jenkins-Crumb'] = $crumb
Invoke-RestMethod 'http://localhost:8081/job/mall-cicd/buildWithParameters?SCOPE=full&RUN_UI=true&RUN_PERF=false' -Method Post -Headers $h
```

---

## 六、报告与产物

| 产物 | 位置 |
|---|---|
| **Allure 报告（插件）** | 构建页左侧「Allure Report」入口：`/job/<job>/<build>/allure/`；趋势图：`/job/<job>/<build>/allure/widgets/history-trend.json` |
| Allure 项目级报告 | `/job/<job>/allure/`（聚合最近一次，带历史趋势） |
| Allure HTML（CLI 生成） | 容器内 `/var/jenkins_home/mall/reports/allure-report/index.html`，同时作为构建产物归档 |
| JMeter HTML 报告 | `/workspace/reports/perf/<场景>-<tag>-<并发>u/report/index.html` |
| 运行日志 | `/workspace/reports/logs/run.log` |
| 构建归档 | Jenkins → 构建 → Artifacts（`reports/allure-report/**`、`reports/perf/**`） |

> UI 用例失败时的截图 / DOM / 控制台日志同样落在 `reports/ui-evidence/`，并作为 Allure 附件保存。


---

## 六·二、Allure 集成说明

Jenkins 里是**双轨**的：

| 方式 | 作用 |
|---|---|
| Allure Jenkins 插件（`allure` 步骤） | 构建页报告入口、项目级报告、**历史趋势图**（通过率/TPS/缺陷数按构建对比） |
| Allure CLI（`allure generate`） | 生成一份纯静态 HTML 放 `reports/allure-report`，随构建产物归档，便于离线查看/发给外部 |

插件配置：
- 插件在镜像构建期安装（`plugins.txt` 里 `allure-jenkins-plugin:latest`）；
- 命令行复用镜像内预装的 `/opt/allure`（JCasC `tool.allure.installations`），**不会每次构建去 Maven 中央仓库下载**；
- 流水线里的步骤：

```groovy
catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
    allure includeProperties: false, jdk: '', results: [[path: 'reports/allure-results']]
}
```

实测（构建 #1、#2）：

```
[Allure] No installation selected, using the only available: allure
Using Allure CLI 2.30.0 from installation 'allure'
Using Allure CLI: /opt/allure/bin/allure
Allure report was successfully generated.
Archiving Allure report via ArtifactManager…
```

验证点：
- `GET /job/mall-cicd/2/allure/` → 200（构建页报告入口）
- `GET /job/mall-cicd/allure/` → 200（项目级报告）
- `GET /job/mall-cicd/2/allure/widgets/history-trend.json` → 返回 2 次构建的历史（`buildOrder: 2, passed: 30, skipped: 4`）

---

## 七、构建历史（实测）

| 构建 | 参数 | 结果 | 耗时 | 说明 |
|---|---|---|---|---|
| #1 | SCOPE=smoke, RUN_UI=true | **SUCCESS** | 153.7s | 接口冒烟 30 passed / 4 xfail；UI 10 passed / 1 xfail；Allure 生成成功；归档 1981 个文件 |
| #2 | SCOPE=full, RUN_UI=true, RUN_PERF=true | **SUCCESS** | 496.0s | 全量接口 + UI + 5 场景性能基线（每场景 30s），全部阶段走通 |
| #3 | SCOPE=full, RUN_UI=false | SUCCESS | 158.4s | 全量接口 131 passed / 1 skipped / 20 xfail；归档 3582 个文件 |

**一次真实的偶发失败**：某次 `SCOPE=full` 构建中，9 条下单链路用例失败（`generateOrder` 返回 500，
日志显示订单 `total_amount=0`、明细为空，即确认单拿到的是空购物车）。同环境复跑、以及在 Jenkins 容器内单独重跑
`tests/portal/test_portal_order.py` 均全部通过（13 passed / 9 xfail），判定为下单链路对 DB/Redis 状态敏感的偶发问题。
处理方式：在「接口全量」阶段包一层 `retry(2)`，重试一次再判定失败，避免偶发问题把整条流水线刷红。

> 后续可引入 pytest-rerunfailures 做用例级重试，并在用例里对「确认单购物车为空」加显式断言，定位这类问题会更快。

## 八、常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| 构建 0.5s 就失败，报 `No such DSL method '﻿pipeline'` | Jenkinsfile 带 UTF-8 BOM，`pipeline` 变成 `\ufeffpipeline` | 用无 BOM 的 UTF-8 保存 Jenkinsfile（本仓库已固化） |
| 构建报 `script not yet approved` | 任务 XML 里 `<sandbox>false</sandbox>` | 改为 `true`（create_job.py 默认 true） |
| 构建报 `ModuleNotFoundError: selenium` | CI 镜像 requirements 未含 selenium | requirements.txt 增加 selenium 后重建镜像 |
| 插件数量为 0 / 无 Pipeline 步骤 | 镜像未在构建期安装插件 | Dockerfile 用 `jenkins-plugin-cli` 安装（已内置） |
| pip 安装 403 | 镜像内 pip 源被限流 | Dockerfile 改用阿里云 pypi 源 |
| `AccessDeniedException: /workspace@tmp` | Jenkins 会在工作目录旁建 `@tmp`，挂在 `/workspace` 或 `/home/jenkins` 下时父目录不可写 | 工作目录挂到 `/var/jenkins_home/mall`（jenkins 用户可写） |
| `mall-cicd is not parameterized` | 任务 XML 未声明参数，参数只在 Jenkinsfile 里 | 在 job XML 的 `<properties>` 中声明三个参数 |
| `Nothing is submitted` | 对参数化任务调用 `/build` | 用 `buildWithParameters` |
| 归档提示 `doesn't match anything` | `archiveArtifacts` 在 Jenkins 默认 workspace 下找文件，而实际产物在挂载目录 | 用 `dir('/var/jenkins_home/mall') { archiveArtifacts ... }` 包裹 |
| UI 用例连不上浏览器 | selenium 容器未启动 / 不在同一网络 | `docker compose -f jenkins/docker-compose.jenkins.yml ps`，确认 join `mall-test_mall-net` |
| 容器内访问不到被测服务 | 网络配置错误 | `MALL_ENV=ci` 指向 `mall-admin:8080` 等服务名，必须与 mall-test 同网络 |
| 端口 8080 冲突 | 宿主机 pagewatch 占用 | Jenkins 映射到 8081（见 compose） |

---

## 九、后续增强（未做）

- 定时任务：工作日 09:00 跑 full+UI，每日 02:00 跑性能基线（Jenkins cron 触发器，当前用参数手动触发）；
- 邮件/钉钉通知：`email-ext` 插件或 webhook；
- 质量门禁：接口失败率 > 0 或 P0 用例失败即阻断合并（需接入 Git/PR 触发）；
- 制品留存策略：构建归档保留 20 次（`buildDiscarder` 已配置）。
