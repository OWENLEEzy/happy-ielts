# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**DynamicLingo** — 本地 AI 英语读写飞轮。每日自动抓取文章 → 深读高亮 → 写作任务 → 间隔复习生词。

## Commands

```bash
# 开发
task dev:backend          # FastAPI on :8000 (--reload)
task dev:frontend         # Next.js on :3000

# 测试
task test                                          # 全部后端测试
uv run pytest backend/tests/ -v                    # 全部后端测试（详细）
uv run pytest backend/tests/test_models.py -v      # 单文件示例
cd frontend && npx playwright test                 # E2E 测试

# 检查 / 格式化
task check                # ruff + mypy + eslint + tsc（并行）
task fix                  # 自动修复所有格式问题

# 类型同步（改 models.py 后必跑）
task generate-types       # Pydantic → frontend/types/api.ts

# 首次 setup
uv sync
task install-hooks
cd frontend && npm install
cp .env.example .env
```

## Architecture

三个完全解耦的 loop，共享同一个 `./db.sqlite3`：

```
Slow loop (background, daily 2am cron)       Fast loop (foreground, SSE)
──────────────────────────────────────       ──────────────────────────────
DeepAgent Planner                            LangGraph Tutor Graph
  load_user_profile                            route_start  (Command routing)
  → TavilySearchResults                               → spaced_review  (interrupt loop)
  → scrape_article                             → reading  (while True: interrupt)
  → highlight_key_paragraphs                   → writing_task  (interrupt)
  → generate_writing_task                      → evaluate_writing
  → save_daily_lesson                          → save_results
        ↓                                             ↓
   articles / writing_tasks                writing_submissions / vocab_items
        └──────────────── db.sqlite3 ────────────────┘

Post-lesson loop (triggered by save_results)
────────────────────────────────────────────
DeepAgent Reflect
  analyze writing_submissions + vocab_items
  → generate ReflectHandoff (strength/weakness summary)
  → trigger Planner with handoff for next lesson
```

**两个 SQLite 文件：**
- `db.sqlite3` — 应用数据（articles、writing_tasks、submissions、vocab_items）
- `checkpoints.sqlite3` — LangGraph checkpoint（tutor graph 和 onboarding 的 thread 状态）

**前端路由：** Next.js `app/api/[...proxy]/route.ts` 透传到 FastAPI，无需 CORS 配置。

**SSE 模式：** 所有实时交互走 `POST /api/lesson/action` → `Command(resume=action)` → `stream_mode="custom"`，**不用 WebSocket**。

**Thread ID 约定：**
- Tutor: `date.today().isoformat()`（今日唯一）
- Planner: `f"planner-{date.today().isoformat()}"`
- Onboarding: `"onboarding"`（固定）

**Checkpointer 单例：** `AsyncSqliteSaver`（`langgraph.checkpoint.sqlite.aio`）在 `main.py` lifespan 中创建一次，通过 `app.state.checkpointer` 传给所有 agent 和图，**不在各模块内单独 `from_conn_string()`**。

**Cron 调度：** `APScheduler` 在 lifespan 中启动，每日 02:00 执行 `_cron_prepare_next()`，若次日课程未就绪则触发 Planner。

## 后端关键模块

| 文件 | 用途 |
|------|------|
| `main.py` | FastAPI app + lifespan（checkpointer 单例 + cron scheduler） |
| `models.py` | 所有 Pydantic 模型——改后必跑 `task generate-types` |
| `database.py` | SQLite CRUD 封装（articles、tasks、submissions、vocab） |
| `orchestrator.py` | 冷路径/暖路径路由，`_start_planner_thread()` 启动后台规划 |
| `student_model.py` | 学生画像（水平、兴趣、进度），持久化到 `student_model.json` |
| `curriculum.py` | 课程路径生成逻辑，基于 student model 选择难度和主题 |
| `memory.py` | 嵌入 + 向量检索，为 LLM 提供个性化上下文 |
| `fsrs_engine.py` | FSRS 间隔复习算法，计算生词复习时机 |
| `llm.py` | `ChatTongyi(model="qwen-max")` 单例初始化 |
| `planner/agent.py` | DeepAgent Planner（每日文章生成） |
| `planner/tools.py` | Tavily 搜索、网页抓取、段落高亮提取 |
| `tutor/graph.py` | LangGraph Tutor Graph 定义 |
| `tutor/nodes.py` | 节点实现（route_start、reading、writing_task、evaluate_writing、save_results） |
| `onboarding/agent.py` | DeepAgent Onboarding（用户初始化） |
| `reflect/agent.py` | DeepAgent Reflect（写作复盘 → 生成 ReflectHandoff） |

## LangChain / LangGraph / DeepAgents 使用规则

### 用哪个框架

| 场景 | 框架 |
|------|------|
| 需要精确控制 interrupt 位置、SSE streaming | **LangGraph** (Tutor Graph) |
| 开放式多步任务、可以让模型自主规划 | **DeepAgents** (Planner / Onboarding / Reflect) |
| 单次 LLM 调用、structured output | **LangChain** (`@tool` + `with_structured_output`) |

### 必须调用的 langchain-skills（写代码前先 invoke）

| 场景 | Skill |
|------|-------|
| 选框架前 | `langchain-skills:framework-selection` |
| 写任何 LangGraph 节点 | `langchain-skills:langgraph-fundamentals` |
| 写 `interrupt()` / `Command(resume=...)` | `langchain-skills:langgraph-human-in-the-loop` |
| 写 checkpointer / thread_id / Store | `langchain-skills:langgraph-persistence` |
| 写 `create_deep_agent()` | `langchain-skills:deep-agents-core` |
| 写多 agent 编排 / subagent | `langchain-skills:deep-agents-orchestration` |
| 安装或升级依赖 | `langchain-skills:langchain-dependencies` |
| 写 `with_structured_output` / middleware | `langchain-skills:langchain-middleware` |

### LangGraph 关键约定（必须遵守）

**interrupt() 幂等性：** 节点 resume 时从函数顶部重新执行，`interrupt()` 之前的所有代码都会重跑。只允许 upsert（不允许 insert）在 `interrupt()` 之前。

**Command routing vs static edge：** 返回 `Command(goto="X")` 的节点**不能**再加 `add_edge(A, "X")`，否则 X 执行两次。

**`while True: interrupt()` 循环：** reading_session 用此模式处理多次用户动作，每次 resume 时节点重跑，`interrupt()` 立刻返回 resume value，继续执行当次动作，然后进入下一次循环再次 `interrupt()`。

**`save_results` 是写作飞轮关键节点：** 必须从 `state["writing_feedback"]` 读取 `WritingFeedback`（由 `evaluate_writing` 写入），调用 `_db.save_writing_submission()` 并将 `chinglish_flags` 中的词写入 `vocab_items`（`source="writing_error"`）。

**RetryPolicy：** `reading` 和 `evaluate_writing` 节点有 `retry_policy=RetryPolicy(max_attempts=3)`（网络抖动兜底），其他节点不需要。

**pre-commit + uv.lock：** `uv run mypy` 会更新 `uv.lock`，导致 pre-commit stash restore 冲突。提交前必须 `git add uv.lock`。

### DeepAgents 关键约定

**系统提示写目标，不写步骤：** Planner 系统提示用 prose 描述目标，不用编号步骤列表（与内置 `write_todos` 中间件冲突）。

**工具签名用 Pydantic 类型：** `save_daily_lesson(article: ArticleCreate, task: WritingTaskCreate)` 而不是 JSON 字符串。LangChain 会自动生成 schema 并做验证。

**structured output 一律用 `with_structured_output()`：** 禁止 `json.loads(response.content)`，模型输出经常带 markdown code fence 导致解析失败。

**Planner 单例：** `get_planner(checkpointer)` 而非 `create_planner()`，避免每次 API 请求泄漏 SQLite 连接。

## Frontend

```bash
cd frontend && npm run dev    # Next.js on :3000
cd frontend && npm run build  # Production build
cd frontend && npx tsc --noEmit  # Type check
```

| 文件 | 用途 |
|------|------|
| `app/api/[...proxy]/route.ts` | 透传代理 → FastAPI :8000（无需 CORS） |
| `app/page.tsx` | 主课程 UI 入口 |
| `hooks/useLesson.ts` | 课程状态管理 hook（SSE 驱动） |
| `lib/sse.ts` | SSE 客户端：`startLesson`、`sendOnboardingMessage` |
| `types/api.ts` | OpenAPI 自动生成——**不要手动编辑** |
| `components/ArticleReader.tsx` | 文章显示 + 关键段落高亮 |
| `components/WritingPanel.tsx` | 写作提交 + feedback SSE 流 |
| `components/FillBlankCard.tsx` | 填空练习交互 |
| `components/FeedbackView.tsx` | 写作反馈展示 |
| `components/WordChip.tsx` | 生词展示（含释义） |

**SSE cleanup：** `useEffect` 必须返回 `AbortController.abort()`，否则切换路由时 stream 泄漏。

## 环境变量

```bash
DASHSCOPE_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
LANGSMITH_TRACING=false
LANGSMITH_API_KEY=ls-...   # 可选，tracing 关闭时不需要
LANGSMITH_PROJECT=dynamiclingo
```

## 模型

全部使用 `qwen-max`，通过 `ChatTongyi(model="qwen-max")` 初始化（`langchain-community`）。
DashScope API key 从 `DASHSCOPE_API_KEY` 环境变量读取。

## 设计文档

- `docs/plans/2026-03-19-dynamiclingo-impl.md` — 权威实现计划（15 个 Task，含完整代码）
- `docs/plans/2026-03-19-dynamiclingo-design.md` — 系统设计（数据模型、API、组件树）
- `docs/plans/2026-03-19-dynamiclingo-prd.md` — 产品需求
- `docs/deployment.md` — 部署记录（Render + Vercel + GAS 保活）
