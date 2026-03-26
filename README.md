# DynamicLingo

**EN** · [中文](#中文)

> A local AI learning flywheel. Pick a language skill or any topic — the system deep-researches a curriculum, delivers interactive lessons (read → quiz → free Q&A), and automatically adapts based on your performance.

---

## Features

| Module | Description |
|--------|-------------|
| **English Mode** | Daily article fetch → highlight reading → writing task → spaced-repetition vocab review |
| **General Learning Mode** | You describe a goal → AI researches it via NotebookLM → generates a structured curriculum → interactive lesson delivery |
| **Adaptive Flywheel** | After each session, a Reflect agent analyses quiz scores, updates a mastery model, and triggers targeted re-research for weak areas |
| **SSE Streaming** | All real-time interaction flows over Server-Sent Events — no WebSocket needed |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  English Mode (existing)                                      │
│                                                               │
│  Slow loop (daily 2 AM)          Fast loop (SSE)             │
│  ─────────────────────           ──────────────────────────  │
│  DeepAgent Planner                LangGraph Tutor Graph      │
│    Tavily search                    route_start              │
│    → scrape article                 → spaced_review (HITL)   │
│    → highlight paragraphs           → reading (HITL)         │
│    → generate writing task          → writing_task (HITL)    │
│    → save_daily_lesson              → evaluate_writing       │
│                                     → save_results           │
│                                            ↓                 │
│                              DeepAgent Reflect               │
│                                → ReflectHandoff              │
│                                → triggers Planner            │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  General Learning Mode (new)                                  │
│                                                               │
│  Onboarding          Research            Lesson              │
│  ────────────        ────────────────    ────────────────    │
│  DeepAgent           DeepAgent loop      LangGraph           │
│  Onboarding          Researcher          GeneralLessonGraph  │
│    chat interview      broad sweep         reading (HITL)    │
│    → UserGoalProfile   → gap analysis      → quiz (HITL)     │
│    → draft map         → fill gaps         → free_qa (HITL)  │
│                        → mind map          → save_results    │
│                              ↓                    ↓          │
│                        Extractor           Reflect agent     │
│                          per-lesson          mastery model   │
│                          study guide         weak dims →     │
│                          quiz + cards        re-research     │
└─────────────────────────────────────────────────────────────┘

Shared: SQLite (db.sqlite3) · LangGraph checkpoints (checkpoints.sqlite3)
        ChatTongyi (qwen-max) · Next.js proxy → FastAPI
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | `qwen-max` via `langchain-community` ChatTongyi |
| Orchestration | LangGraph 1.x (HITL graphs) + DeepAgents (open-ended tasks) |
| Knowledge store | NotebookLM via `notebooklm-py` CLI wrapper |
| Backend | FastAPI + APScheduler + SQLite |
| Frontend | Next.js 14 (App Router) + Tailwind CSS + Framer Motion |
| Search | Tavily API |
| Spaced repetition | FSRS algorithm (`fsrs` package) |

---

## Quick Start

### Prerequisites

- Python 3.12+, `uv`
- Node.js 18+
- API keys: `DASHSCOPE_API_KEY`, `TAVILY_API_KEY`
- (Optional) `LANGSMITH_API_KEY` for tracing

### Setup

```bash
# Clone and install
git clone <repo>
cd language-teacher

uv sync
cd frontend && npm install && cd ..

cp .env.example .env
# Fill in DASHSCOPE_API_KEY and TAVILY_API_KEY

# Install git hooks
task install-hooks

# One-time: authenticate NotebookLM (General Learning mode)
notebooklm login
```

### Run

```bash
task dev:backend    # FastAPI on :8000
task dev:frontend   # Next.js on :3000
```

Open [http://localhost:3000](http://localhost:3000).

---

## Development Commands

```bash
# Tests
task test                          # all backend tests
uv run pytest backend/tests/ -v    # verbose

# Lint & type check
task check                         # ruff + mypy + eslint + tsc (parallel)
task fix                           # auto-fix all formatting

# Sync TypeScript types after editing models.py
task generate-types
```

---

## Project Structure

```
backend/
├── main.py              # FastAPI app + lifespan (checkpointer, APScheduler)
├── models.py            # All Pydantic models
├── database.py          # SQLite CRUD
├── llm.py               # ChatTongyi singleton
├── planner/             # DeepAgent: daily article generation
├── tutor/               # LangGraph: English lesson graph
├── onboarding/          # DeepAgent: English onboarding
├── reflect/             # DeepAgent: writing reflection
└── general/             # General Learning mode
    ├── onboarding.py    # DeepAgent: goal interview + draft map
    ├── researcher.py    # Async research loop (NotebookLM)
    ├── extractor.py     # Per-lesson content extraction
    ├── nodes.py         # LangGraph nodes (reading/quiz/free_qa)
    ├── graph.py         # GeneralLessonGraph definition
    ├── reflect.py       # Mastery model + re-research trigger
    └── notebooklm.py    # Async CLI wrapper for notebooklm-py

frontend/
├── app/
│   ├── lesson/          # English lesson UI
│   ├── onboarding/      # English onboarding chat
│   └── learn/           # General Learning mode
│       ├── page.tsx          # Mode selection
│       ├── onboarding/       # Goal interview chat
│       ├── preparing/[id]/   # Research progress page
│       └── [projectId]/
│           ├── page.tsx                    # Curriculum view
│           └── lesson/[lessonId]/page.tsx  # Lesson delivery
├── hooks/
│   ├── useLesson.ts         # English lesson state (SSE)
│   └── useGeneralLesson.ts  # General lesson state (SSE)
└── lib/sse.ts               # SSE client helpers
```

---

## Environment Variables

```bash
DASHSCOPE_API_KEY=sk-...       # Required: Qwen model access
TAVILY_API_KEY=tvly-...        # Required: web search
LANGSMITH_TRACING=false        # Optional: set true to enable tracing
LANGSMITH_API_KEY=ls-...       # Optional: required if tracing=true
LANGSMITH_PROJECT=dynamiclingo
```

---

## Deployment

| Service | Platform | URL |
|---------|----------|-----|
| Backend (FastAPI) | Render (free tier) | https://happy-ielts.onrender.com |
| Frontend (Next.js) | Vercel | https://frontend-chi-opal-61.vercel.app |

See [`docs/deployment.md`](docs/deployment.md) for the full deployment guide including the Google Apps Script keep-alive setup for Render's free tier.

---

---

# 中文

> 本地 AI 学习飞轮。选择语言技能或任意主题——系统自动深度研究课程、生成互动课堂（阅读 → 测验 → 自由问答），并根据学习表现自适应调整。

---

## 功能模块

| 模块 | 说明 |
|------|------|
| **英语模式** | 每日自动抓取文章 → 深读高亮 → 写作任务 → 间隔复习生词 |
| **通用学习模式** | 你描述学习目标 → AI 通过 NotebookLM 深度研究 → 生成结构化课程 → 交互式课堂 |
| **自适应飞轮** | 每节课后，Reflect 智能体分析测验分数、更新掌握度模型，并对薄弱章节触发定向补研究 |
| **SSE 流式传输** | 所有实时交互通过 Server-Sent Events 完成，无需 WebSocket |

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│  英语模式                                                      │
│                                                               │
│  慢速循环（每日 2AM）         快速循环（SSE）                   │
│  ─────────────────────       ─────────────────────────────  │
│  DeepAgent Planner            LangGraph Tutor Graph          │
│    Tavily 搜索                  route_start                  │
│    → 抓取文章                   → 生词复习（HITL）            │
│    → 提取高亮段落               → 阅读（HITL）                │
│    → 生成写作任务               → 写作（HITL）                │
│    → 保存今日课程               → 评估写作                    │
│                                 → 保存结果                   │
│                                       ↓                      │
│                             DeepAgent Reflect                │
│                               → 生成 ReflectHandoff          │
│                               → 触发 Planner                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  通用学习模式                                                   │
│                                                               │
│  入门访谈          备课研究                上课                 │
│  ────────────      ────────────────────    ────────────────  │
│  DeepAgent         DeepAgent 循环          LangGraph         │
│  Onboarding        Researcher              GeneralLesson     │
│    对话了解目标      宽泛扫描                 阅读（HITL）      │
│    → 目标画像        → 缺口分析               → 测验（HITL）   │
│    → 草稿课程图      → 补充研究               → 问答（HITL）   │
│                     → 生成知识地图            → 保存结果       │
│                           ↓                       ↓          │
│                     Extractor               Reflect 智能体   │
│                       每节课提取              掌握度模型       │
│                       学习指南                薄弱维度 →      │
│                       测验 + 闪卡             定向补研究       │
└─────────────────────────────────────────────────────────────┘

共享：SQLite (db.sqlite3) · LangGraph 检查点 (checkpoints.sqlite3)
      ChatTongyi (qwen-max) · Next.js 代理 → FastAPI
```

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 大模型 | `qwen-max`（通过 `langchain-community` ChatTongyi） |
| 编排 | LangGraph 1.x（HITL 图）+ DeepAgents（开放式多步任务） |
| 知识库 | NotebookLM（通过 `notebooklm-py` CLI 封装） |
| 后端 | FastAPI + APScheduler + SQLite |
| 前端 | Next.js 14（App Router）+ Tailwind CSS + Framer Motion |
| 搜索 | Tavily API |
| 间隔复习 | FSRS 算法（`fsrs` 包） |

---

## 快速开始

### 前置条件

- Python 3.12+、`uv`
- Node.js 18+
- API 密钥：`DASHSCOPE_API_KEY`、`TAVILY_API_KEY`
- （可选）`LANGSMITH_API_KEY` 用于链路追踪

### 安装

```bash
git clone <repo>
cd language-teacher

uv sync
cd frontend && npm install && cd ..

cp .env.example .env
# 填写 DASHSCOPE_API_KEY 和 TAVILY_API_KEY

# 安装 git hooks
task install-hooks

# 一次性：NotebookLM 登录（通用学习模式需要）
notebooklm login
```

### 启动

```bash
task dev:backend    # FastAPI :8000
task dev:frontend   # Next.js :3000
```

访问 [http://localhost:3000](http://localhost:3000)。

---

## 开发命令

```bash
# 测试
task test                          # 全部后端测试
uv run pytest backend/tests/ -v    # 详细模式

# 代码检查 & 类型检查
task check                         # ruff + mypy + eslint + tsc（并行）
task fix                           # 自动修复所有格式问题

# 修改 models.py 后同步 TypeScript 类型
task generate-types
```

---

## 项目结构

```
backend/
├── main.py              # FastAPI app + lifespan（checkpointer、APScheduler）
├── models.py            # 所有 Pydantic 模型
├── database.py          # SQLite CRUD 封装
├── llm.py               # ChatTongyi 单例
├── planner/             # DeepAgent：每日文章生成
├── tutor/               # LangGraph：英语课程图
├── onboarding/          # DeepAgent：英语入门访谈
├── reflect/             # DeepAgent：写作复盘
└── general/             # 通用学习模式
    ├── onboarding.py    # DeepAgent：目标访谈 + 草稿课程图
    ├── researcher.py    # 异步备课循环（NotebookLM）
    ├── extractor.py     # 逐节课内容提取
    ├── nodes.py         # LangGraph 节点（阅读/测验/问答）
    ├── graph.py         # GeneralLessonGraph 定义
    ├── reflect.py       # 掌握度模型 + 定向补研究触发
    └── notebooklm.py    # notebooklm-py CLI 异步封装

frontend/
├── app/
│   ├── lesson/          # 英语课堂 UI
│   ├── onboarding/      # 英语入门对话
│   └── learn/           # 通用学习模式
│       ├── page.tsx               # 模式选择
│       ├── onboarding/            # 目标访谈对话
│       ├── preparing/[id]/        # 备课进度页
│       └── [projectId]/
│           ├── page.tsx                    # 课程大纲
│           └── lesson/[lessonId]/page.tsx  # 课堂交互
├── hooks/
│   ├── useLesson.ts         # 英语课堂状态（SSE）
│   └── useGeneralLesson.ts  # 通用课堂状态（SSE）
└── lib/sse.ts               # SSE 客户端工具函数
```

---

## 环境变量

```bash
DASHSCOPE_API_KEY=sk-...       # 必填：Qwen 模型访问
TAVILY_API_KEY=tvly-...        # 必填：网页搜索
LANGSMITH_TRACING=false        # 可选：true 开启链路追踪
LANGSMITH_API_KEY=ls-...       # 可选：tracing=true 时需要
LANGSMITH_PROJECT=dynamiclingo
```

---

## 部署信息

| 服务 | 平台 | 地址 |
|------|------|------|
| 后端（FastAPI） | Render（免费层） | https://happy-ielts.onrender.com |
| 前端（Next.js） | Vercel | https://frontend-chi-opal-61.vercel.app |

完整部署指南（含 Google Apps Script 保活方案）见 [`docs/deployment.md`](docs/deployment.md)。
