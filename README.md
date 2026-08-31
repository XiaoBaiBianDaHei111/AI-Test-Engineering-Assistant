# AI Test Workflow Automation

覆盖测试工程师「需求评审 → 测试点提取 → 用例设计 → 用例评审 → 自动化执行 → 失败分析 → 测试报告 → 质量总结」全流程的 AI 辅助自动化测试平台。

AI 在每个环节产出**结构化、可校验、可人工干预**的中间产物，而非"输入一句话生成一个脚本"的单点工具。

## 项目亮点

- **完整工作流闭环**：从 PRD 到质量总结的端到端自动化，各环节产物入库可追溯、可人工评审介入。
- **真实 AI 链路**：DeepSeek（OpenAI 兼容）结构化输出，含容错 JSON 提取、Pydantic schema 校验、修复重生成（≤2 次）、AI 审计日志（token/延迟/状态）。
- **双执行链路统一模型**：UI（Playwright）与 API（httpx）两条执行链路共用 `TestRun / TestRunCase / TestStepResult` 数据模型，统一进入失败分析与报告。
- **失败分析规则层先行**：Python Playwright 强签名表锁定 `BROKEN_LOCATOR`（0 次 LLM 调用），LLM 兜底四类分类（BROKEN_LOCATOR / REAL_BUG / FLAKY / ENV_ISSUE），置信度门控强制人工确认（needs_human）。
- **执行证据全量采集**：逐步截图、console 消息、network 响应、Playwright trace.zip，并提供 Trace 解析时间线。
- **单文件自包含 HTML 报告**：内联 CSS（离线可开）、证据内嵌、XSS 转义；JSON / Markdown 导出。
- **Docker Compose 一键部署**：PostgreSQL + 后端 + 前端三服务。

## 架构

```text
┌─────────────────────────────────────────────────────────────────────┐
│                         React 18 + TypeScript (Vite)                │
│  需求 / 测试点 / 用例 / 评审 / 执行 / 证据 / 失败分析 / 报告 / 接口用例 │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ REST /api/*
┌──────────────────────────────▼──────────────────────────────────────┐
│                    FastAPI 后端 (backend/app)                       │
│  assets(CRUD+状态机)  ai(Agent+结构化输出+审计)  analysis(规则/统计) │
│  execution(PlaywrightDriver/ApiRunner)  api(routes)                 │
│  报告生成(report_html/markdown/stats)   demo_app + demo_api         │
└──────┬───────────────────────────────┬──────────────────────────────┘
       │ SQLAlchemy 2.0               │ artifacts/
┌──────▼──────────────┐        ┌──────▼──────────────────────────────┐
│ PostgreSQL / SQLite │        │ scripts/ evidence/ traces/ reports/  │
└─────────────────────┘        └─────────────────────────────────────┘
       │ LLM (OpenAI-compatible: DeepSeek)
```

- **分层**：`api`（路由）→ `services/{assets,ai,analysis}`（业务/Agent/规则）→ `models`（ORM）→ DB；`execution`（执行器）与 `demo_app`/`demo_api`（演示目标）独立。
- **状态机**：Requirement / TestPoint / TestCase / GenerationRun / TestRun / FailureAnalysis 均服务层强制合法流转，非法流转返回 409 `INVALID_TRANSITION`。

## 技术栈

| 层       | 技术                                                                |
| -------- | ------------------------------------------------------------------- |
| 后端     | Python 3.11+ / FastAPI / SQLAlchemy 2.0 / Pydantic v2               |
| 数据库   | PostgreSQL（Docker，`localhost:5433`）；SQLite 兜底                 |
| 前端     | React 18 / TypeScript / Vite                                        |
| UI 执行  | Playwright（Python sync API，headless chromium）                    |
| API 执行 | httpx                                                               |
| AI       | DeepSeek（OpenAI 兼容，httpx 直连，`response_format: json_object`） |
| 部署     | Docker Compose / nginx                                              |

## 功能模块

### 测试资产管理

- `Project` / `Requirement` / `TestPoint` / `TestCase`(+步骤) / `APITestCase` 的 CRUD、评审记录与状态机。
- 用例 `case_id`（如 `TC-001`）项目内唯一；AI 生成的关联（requirement/test_point）由系统注入，不信任 AI 输出。

### AI 需求分析与测试点提取

- 粘贴 PRD → 超长分段 → 结构化需求（验收标准 / 风险 / gap / 歧义）→ 人工确认（Gate 1）。
- 已确认需求 → 测试点提取（technique 受限枚举）→ 人工确认（Gate 2）。
- 每次 Agent 调用记录审计日志（agent / schema 版本 / tokens / latency / status）。

### AI 用例生成与评审

- 单测试点 → 1~3 条结构化用例（title/priority/type/precondition/steps/test_data），批量生成 + 进度状态（`GenerationRun`）+ 批内/库内去重。
- 用例评审工作流：提交 → AI 三维评分（completeness/accuracy/executability）→ 通过/退回；verdict 由系统按规则重算（任一维度 ≤2 → needs_work），不信任 LLM 自评。
- 可执行门控（Gate 3）：仅 `approved` 用例可执行（409 `CASE_NOT_APPROVED`）。

### 脚本生成与自动化执行

- AI 生成结构化 Playwright 步骤（description + 单表达式 code），系统装配骨架脚本并**静态校验**（语法 / import 白名单 / 禁用 token / 末步断言 / 首步 goto），失败自动修复重生成 ≤2 次。
- **外部站点契约**：按 `BASE_URL` 主机名区分——本地目标拼 `/demo/?qaMode=`，外部站点仅 `page.goto(BASE_URL)`；定位器优先 role / label / CSS 类，仅目标确实存在 data-testid 时才用 `get_by_test_id`。
- **登录前置注入**：用例 test_data 携带凭据时，系统确定性注入登录步骤（首步 goto 之后，不依赖 AI 输出）。
- 逐步执行并记录 `TestStepResult`（状态 / 消息 / 耗时 / element_found）；脚本落盘可查看/编辑/重跑；run 支持取消与复用脚本重跑。

### 执行证据采集与 Trace 解析

- 每步骤截图 + console 消息 + network 响应 + trace.zip，按冻结布局落盘 `artifacts/<run_id>/...`；证据写入失败不阻断用例结果。
- Trace 解析：NDJSON 动作配对 / 请求响应配对 / 快照引用，自动入库并提供时间线视图。
- 保留策略：`scripts/cleanup_evidence.py` 按 `EVIDENCE_RETENTION_DAYS`（默认 30 天）清理过期 run 目录（`--dry-run` 幂等）。

### 失败分析

- **规则层**：10 个 Python Playwright 强签名（`waiting for get_by_test_id(` / `strict mode violation` / `resolved to 0 elements` 等）锁定 `BROKEN_LOCATOR`（固定置信度 0.93，0 次 LLM 调用）；断言不匹配 / `get_by_text` 缺失不锁（交 LLM）。
- **LLM 层**：四类分类 + 置信度 + 原因 + 修复建议；容错提取 + 校验 + 修复重试。
- **置信度门控**：LLM 置信度 < 0.7 → `needs_human=True` 强制人工确认；规则层 `needs_human=False`。
- run 中 failed/blocked 用例自动触发分析（隔离，失败不阻断 run，前端可重试）。

### 测试报告与质量总结

- run 完成后自动生成 HTML 报告（或手动重新生成）：通过率、按优先级通过率、失败分类分布、用例明细（状态/耗时/错误/失败分析/证据引用）。
- 质量总结 Agent（仅统计字段输入，禁编造）：`recommendation`（GO / CONDITIONAL_GO / NO_GO）与 `overall_score` 由规则重算。
- 导出：JSON / Markdown（由报告数据渲染，无 AI）。

### 接口测试

- `APITestCase`：method / url（相对路径，运行期拼 base_url）/ headers / body / assertions（status / json_field / response_time / header）。
- AI 生成接口用例（成功 / 错误状态码 / 参数缺失 / 认证）；httpx 逐步执行 + 断言 → 统一的 `TestRunCase`（kind=api）。
- UI 与 API 用例可混合同一个 run（`api_case_ids` + 用例 ID），统一失败分析与报告。

### 演示目标应用

- 后端托管静态 SPA（登录 + 任务管理，`/demo`）+ 确定性 demo API（`/api/demo-api/*`），凭据 `testuser / Test@1234`。
- `?qaMode=` 故障注入：none / selector-change / logic-bug / slow-network / auth-break——用于演示失败分析与报告链路。

## 快速开始

### 方式一：Docker Compose（推荐）

前置：安装 Docker Desktop 并启动。

```bash
docker compose up --build          # 数据库 + 后端 + 前端
# 前端 http://localhost:3000
# 后端 API http://localhost:8000（Swagger: /docs）
# PostgreSQL: 宿主侧 localhost:5433（compose 映射 5433:5432）
docker compose exec backend python scripts/seed.py   # （可选）灌入演示数据
curl http://localhost:8000/api/health
```

### 方式二：本地开发

```bash
# 后端（SQLite 兜底）
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate ; macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000

# 前端（另开终端，自动代理 /api → :8000）
cd frontend
npm install
npm run dev     # http://localhost:5173

# 灌入演示数据
cd backend && python scripts/seed.py
```

### LLM 配置（真实 DeepSeek）

在仓库根目录 `.env`（复制自 `.env.example`）或环境变量中设置：

```bash
LLM_API_KEY=<你的 DeepSeek API Key>
LLM_MODEL=deepseek-chat        # 可选，默认 deepseek-chat
LLM_BASE_URL=https://api.deepseek.com/v1   # 可选
```

> 真实 AI 路径必须配置 key；执行环节需安装浏览器（`playwright install chromium`）。未配置时对应路径会明确报错，无零密钥兜底。

### 一键端到端演示

```bash
cd backend
.\scripts\demo.ps1        # Windows
# 或 bash scripts/demo.sh  # Linux/macOS
# → 输出 "DEMO PASSED"（health → 项目 → PRD 分析 → 测试点 → 用例生成 → 评审 → 执行 → 报告 → 质量总结）
```

## 测试

```bash
cd backend
pytest          # 单元门禁（默认跳过 real/e2e：零 key、零浏览器）
pytest -m real  # 真实集成（需 LLM_API_KEY；浏览器用例需 PLAYWRIGHT_BROWSERS_PATH）
pytest -m e2e   # 真实浏览器端到端（需浏览器 + 后端在跑，E2E_BASE_URL 默认 http://localhost:8000）
```

- **CI（`.github/workflows/ci.yml`）**：push / PR 自动执行——后端 ruff + 单元门禁 + 覆盖率；前端 tsc 类型检查 + 构建。零密钥、永不依赖外部服务。
- **real-smoke（`.github/workflows/real-smoke.yml`）**：手动或每周触发，真实 DeepSeek + Playwright 冒烟（需配置 GitHub Secret `DEEPSEEK_API_KEY`）。

## 目录结构

```text
ai-test-workflow-automation/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI 入口
│   │   ├── core/             # 配置 / 数据库 / schema 检查 / 日志 / 异常
│   │   ├── models/           # SQLAlchemy 模型
│   │   ├── schemas/          # Pydantic 请求/响应 + AI 输出 schema
│   │   ├── api/              # 路由（assets / ai）
│   │   ├── services/
│   │   │   ├── assets/       # 资产 CRUD + 状态机
│   │   │   ├── ai/           # llm_client / structured / audit / agents / prompts / dom_scraper
│   │   │   └── analysis/     # 规则分类 / 失败上下文 / 报告统计
│   │   ├── execution/        # PlaywrightDriver / ApiRunner
│   │   ├── demo_app/         # 演示目标 SPA（/demo）
│   │   └── demo_api.py       # 确定性演示 API
│   ├── scripts/              # seed / demo / reset_db / cleanup_evidence / capture_qa_mode_errors
│   ├── tests/                # pytest（unit + real + e2e）
│   └── Dockerfile
├── frontend/                 # React + TypeScript + Vite
│   ├── src/pages/            # 项目 / 需求 / 测试点 / 用例 / 执行 / 证据 / 失败分析 / 报告 / 接口用例
│   ├── src/api/              # API client
│   └── Dockerfile
├── docker-compose.yml
├── .github/workflows/        # ci.yml / real-smoke.yml
└── .env.example
```

## API 概览

所有路径带 `/api` 前缀，错误统一为 `{"code","message","detail"}`。

### 资产

| 方法             | 路径                                                | 用途                             |
| ---------------- | --------------------------------------------------- | -------------------------------- |
| GET              | `/api/health`                                       | 健康检查                         |
| GET/POST         | `/api/projects`                                     | 项目列表 / 创建                  |
| GET/PATCH/DELETE | `/api/projects/{id}`                                | 项目详情 / 编辑 / 删除           |
| GET/POST         | `/api/projects/{id}/requirements`                   | 需求列表 / 创建                  |
| GET/PATCH/DELETE | `/api/requirements/{id}`                            | 需求详情 / 编辑 / 删除           |
| GET/POST         | `/api/requirements/{id}/test-points`                | 测试点列表 / 创建                |
| GET/PATCH/DELETE | `/api/test-points/{id}`                             | 测试点详情 / 编辑 / 删除         |
| GET/POST         | `/api/projects/{id}/test-cases`                     | 用例列表 / 创建                  |
| GET/PATCH/DELETE | `/api/test-cases/{id}`                              | 用例详情 / 编辑 / 删除           |
| POST             | `/api/test-cases/{id}/submit-review`                | 提交评审（draft→pending_review） |
| POST             | `/api/test-cases/{id}/review`                       | 人工评审（通过/退回）            |
| GET              | `/api/projects/{id}/coverage/uncovered-test-points` | 未覆盖测试点清单                 |
| GET              | `/api/projects/{id}/test-cases/executable`          | 可执行用例（仅 approved）        |

### AI

| 方法 | 路径                          | 用途                           |
| ---- | ----------------------------- | ------------------------------ |
| POST | `/api/ai/analyze-requirement` | 需求分析（PRD → 结构化需求）   |
| POST | `/api/ai/extract-test-points` | 测试点提取                     |
| POST | `/api/ai/generate-test-cases` | 用例生成（run 驱动，进度轮询） |
| GET  | `/api/ai/generation-runs`     | 生成 run 历史 / 详情           |
| POST | `/api/ai/review-test-cases`   | AI 用例评审（三维评分）        |
| GET  | `/api/ai/audit`               | AI 审计日志                    |

### 执行 / 证据 / 失败分析 / 报告

| 方法     | 路径                                          | 用途                                   |
| -------- | --------------------------------------------- | -------------------------------------- |
| POST/GET | `/api/runs`                                   | 创建执行（UI+API 混合）/ run 列表      |
| GET      | `/api/runs/{id}`                              | run 详情（状态/进度/每用例状态）       |
| POST     | `/api/runs/{id}/cancel`                       | 取消执行                               |
| GET/PUT  | `/api/runs/{run_id}/cases/{case_id}/script`   | 脚本查看 / 覆盖                        |
| POST     | `/api/runs/{run_id}/cases/{case_id}/rerun`    | 复用脚本重跑（failed/blocked）         |
| GET      | `/api/runs/{run_id}/cases/{case_id}/evidence` | 用例证据列表                           |
| GET      | `/api/evidence/{id}/content`                  | 证据内容（截图/console/network/trace） |
| GET      | `/api/evidence/{id}/trace-parse`              | Trace 解析结果                         |
| GET/POST | `/api/failure-analysis`                       | 失败分析查询 / 重跑                    |
| POST     | `/api/failure-analysis/{id}/confirm`          | 人工确认                               |
| GET/POST | `/api/reports/{run_id}`                       | 报告详情 / 手动生成                    |
| GET      | `/api/reports/{run_id}/html`                  | HTML 报告下载                          |
| GET      | `/api/reports/{run_id}/export`                | 导出`format=json\|markdown`            |
| POST     | `/api/quality-summary/{report_id}`            | 生成质量总结                           |

## License

MIT License — Copyright (c) 2026 AI Test Workflow Automation
