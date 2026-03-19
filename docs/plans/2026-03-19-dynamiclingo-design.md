# DynamicLingo — 系统设计文档

**日期：** 2026-03-19
**定位：** 个人使用，本地 Web App（localhost）
**核心理念：** 基于兴趣的读写双引擎 — "输入 → 消化 → 强输出"认知微型飞轮

---

## 1. 产品愿景

为具备明确职业动机的成人学习者打造的 AI 语言导师。系统每天自动抓取与用户工作和兴趣直接相关的真实英文内容，压缩为精华，驱动一次完整的"精读 + 高压写作"闭环，而非 Duolingo 式的碎片选择题。

**保留的唯一游戏化元素：** 每日开始前，用昨天的错词生成 3 道填空，答完解锁今日新内容。

---

## 2. 核心用户流程

```
每日后台（自动或手动触发）
┌─────────────────────────────────────────────────┐
│ DeepAgent Planner                               │
│   write_todos() → 规划今日内容策略               │
│   search_articles() → Tavily 搜索候选 URL       │
│   scrape_article() → Scrapling 抓取全文          │
│     └── 失败时 fallback → Playwright            │
│   highlight_key_paragraphs() → Claude 标注核心段落序号 + 逻辑类型  │
│   generate_task() → 生成写作任务                │
│   save_daily_lesson() → 写入 SQLite             │
└─────────────────────────────────────────────────┘

每日前台（用户打开 App）
┌─────────────────────────────────────────────────┐
│ Step 1：复习关卡（py-fsrs 到期词）               │
│   → 3 道填空，全部通过才解锁今日内容             │
│                                                 │
│ Step 2：精读                                    │
│   → 展示 Liquid Text（300-500 字精华）          │
│   → 点词 → LangGraph Tutor 上下文释义           │
│   → 点句 → LangGraph Tutor 长难句拆解           │
│                                                 │
│ Step 3：写作任务                                │
│   → Professional 或 IELTS Task 1/2 模式        │
│   → 用户提交英文写作                            │
│                                                 │
│ Step 4：AI 批改（SSE 流式返回）                 │
│   → 语法错误 + Chinglish 识别                   │
│   → 2 个地道重写建议                            │
│   → 错词自动入 py-fsrs 生词本                   │
└─────────────────────────────────────────────────┘

单次学习时长：15-25 分钟
```

---

## 3. 系统架构

### 3.1 两循环分离架构

```
慢循环（DeepAgents）          快循环（LangGraph Tutor）
─────────────────             ────────────────────────
后台异步，分钟级               前台实时，秒级响应
DeepAgent Planner             LangGraph StateGraph
写入 SQLite                   读取 SQLite
─────────────────             ────────────────────────
         ↕ 共享 SQLite 数据库（单向：慢写快读）
```

### 3.2 LangChain / LangGraph / DeepAgents 层级关系

```
LangChain（基础层）
│  模型调用、@tool 装饰器、消息类型、Prompt 模板
│
└── LangGraph（编排层）
    │  StateGraph、节点、边、条件路由、SqliteSaver Checkpointer
    │
    └── DeepAgents（应用层）
        create_deep_agent() = 预装 write_todos + 子智能体 + 上下文压缩的 LangGraph 图
```

| 层 | 用在哪里 | 理由 |
|---|---|---|
| LangChain | 全局基础 | 模型调用、`@tool`、消息类型 |
| LangGraph | Tutor Graph | 需要精确控制每个对话节点和人设 |
| DeepAgents | Planner | 直接用 `write_todos` 规划，无需手写调度逻辑 |

---

## 4. 技术栈

| 层 | 选型 | 说明 |
|---|---|---|
| 包管理 | `uv` | 统一管理 Python 依赖 |
| 后端 API | FastAPI + Uvicorn | 异步高性能，SSE 原生支持 |
| Agent 编排 | LangGraph + DeepAgents | Tutor 用 LangGraph，Planner 用 DeepAgents |
| LLM | Claude Sonnet (claude-sonnet-4-6) | 长文压缩、出题、批改 |
| 爬虫 | Scrapling | 本地执行，失败 fallback Playwright |
| 搜索 | Tavily API | 返回带正文摘要的候选 URL |
| 数据库 | SQLite | 本地零配置，兼作 LangGraph Checkpointer |
| 词汇算法 | `py-fsrs` | 现代间隔重复算法，比 SM-2 更准确 |
| 前端框架 | Next.js + TypeScript | localhost:3000，App Router |
| 前端组件 | shadcn/ui + Tailwind CSS | Radix UI 原语，popover/drawer 开箱即用 |
| 前端动效 | Framer Motion | 批改结果微动效 |
| 前端表单 | React Hook Form + Zod | 写作 textarea 校验，Zod 镜像 Pydantic |
| 前端日期 | date-fns | 格式化复习日期、thread_id |
| 观测平台 | LangSmith | 追踪所有 LangChain/LangGraph 调用，调试 + 费用监控 |
| 流式传输 | SSE (Server-Sent Events) | 单向流，比 WebSocket 更简单 |
| Session 恢复 | `thread_id = 日期字符串` | 天然支持中断恢复，每天一个 checkpoint |

---

## 5. 数据模型

```python
# 用户画像（单行，个人用）
class UserProfile(BaseModel):
    goal: str                    # "无障碍阅读英文技术文档"
    interests: list[str]         # ["TypeScript", "LangGraph", "医美出海"]
    level: int                   # 1-10 词汇量基线
    bandwidth_minutes: int       # 每日可用时长
    writing_mode: Literal["professional", "ielts", "both"]

# 今日文章（DeepAgent Scout 产出）
class Article(BaseModel):
    id: int
    date: str                    # "2026-03-19"
    source_url: str
    original_title: str
    full_text: str               # 完整原文正文
    highlight_indices: list[int] # AI 标注的核心段落序号（0-based，3-5 个）
    article_logic: Literal["compare", "cause_effect", "argumentation"]
    topic_tags: list[str]        # ["TypeScript", "Supabase"]

# 写作任务（从文章动态生成）
class WritingTask(BaseModel):
    id: int
    article_id: int
    mode: Literal["professional", "ielts_task1", "ielts_task2"]
    instruction: str             # 写作指令全文
    min_words: int               # professional: 50, ielts: 100+

# Chinglish 标注（结构化，供 UI 高亮渲染）
class ChinglishFlag(BaseModel):
    original: str                # 用户原句片段，用于 UI 高亮
    issue: Literal["word_choice", "sentence_structure", "logic_connector"]
    explanation_zh: str          # 中文解释，用户看得懂
    native_alternative: str      # 母语者的表达

# 语法错误
class GrammarError(BaseModel):
    original: str
    correction: str
    explanation_zh: str

# 用户写作 + AI 批改结果
class WritingSubmission(BaseModel):
    id: int
    task_id: int
    user_text: str
    overall_score: int           # 1-10
    grammar_errors: list[GrammarError]
    chinglish_flags: list[ChinglishFlag]
    rewrite_suggestions: list[str]  # 2 个完整重写版本
    submitted_at: datetime

# 生词本（py-fsrs 驱动）
class VocabItem(BaseModel):
    id: int
    word: str
    context_sentence: str        # 来源原句
    source: Literal["reading_click", "writing_error"]
    next_review: date            # 冗余字段：用于 SQLite WHERE next_review <= today 快速查询
                                 # fsrs_state["due"] 是权威值，写入时两者保持同步
    fsrs_state: dict             # py-fsrs Card 完整序列化状态
    article_id: int | None       # 溯源
```

**SQLite 表：** `user_profile`, `articles`, `writing_tasks`, `writing_submissions`, `vocab_items`

---

## 6. LangGraph Tutor Graph

### 6.1 State 定义

```python
from typing import Annotated
from typing_extensions import TypedDict
import operator

class TutorState(TypedDict):
    user_profile: UserProfile
    today_article: Article | None
    today_task: WritingTask | None
    review_queue: list[VocabItem]    # py-fsrs 到期词
    review_index: int
    user_writing: str | None
    messages: Annotated[list[BaseMessage], operator.add]  # reducer 必须加
```

### 6.2 节点图

```
[START]
   ↓
[route_start] ──有到期词──→ [spaced_review] ──全部完成──→ [reading]
                                 ↑___Command(goto="spaced_review")__|
                                 (每题用 interrupt() 等待用户输入)

[reading] ──Command(goto="writing_task")──→ [writing_task]
   (interrupt() Validation Loop，点词/点句在节点内循环等待)

[writing_task] ──→ [evaluate_writing] ──→ [save_results] ──→ [END]

注意：reading → writing_task 路由完全由 Command 控制，不加静态 add_edge
```

### 6.3 关键节点实现（LangGraph 正确模式）

```python
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from langgraph.checkpoint.sqlite import SqliteSaver
from typing import Literal

# route_start：Command 同时更新状态 + 路由
def route_start(state: TutorState) -> Command[Literal["spaced_review", "reading"]]:
    due_items = get_due_vocab_items()
    if due_items:
        return Command(
            update={"review_queue": due_items, "review_index": 0},
            goto="spaced_review"
        )
    return Command(goto="reading")

# spaced_review：interrupt() 等待用户答题，Command 控制路由
def spaced_review(state: TutorState) -> Command[Literal["spaced_review", "reading"]]:
    item = state["review_queue"][state["review_index"]]

    # 先用 interrupt() 暂停，向前端发送题目，等待用户作答
    user_answer = interrupt({
        "type": "fill_blank",
        "question": generate_fill_blank_question(item),  # "We ran the ______ on prod."
        "word": item.word,
    })

    # interrupt() 之后处理答案（每次 resume 只执行一次）
    is_correct = user_answer["answer"].strip().lower() == item.word.lower()
    response_seconds = user_answer.get("response_seconds", 10.0)
    rating = map_answer_to_rating(is_correct, response_seconds)
    update_fsrs(item, rating)  # 更新 py-fsrs Card

    next_index = state["review_index"] + 1
    if next_index < len(state["review_queue"]):
        return Command(update={"review_index": next_index}, goto="spaced_review")
    return Command(goto="reading")

# 节点返回 dict（部分更新），不得 mutate 整个 state
def save_results(state: TutorState) -> dict:
    save_submission(state["user_writing"], state["messages"])
    update_vocab_items(state["review_queue"])
    return {"user_writing": None}  # 清空，准备下次

# 编译，以日期为 thread_id 实现中断恢复
graph = (
    StateGraph(TutorState)
    .add_node("route_start", route_start)
    .add_node("spaced_review", spaced_review)
    .add_node("reading", reading_session)
    .add_node("writing_task", writing_task)
    .add_node("evaluate_writing", evaluate_writing)
    .add_node("save_results", save_results)
    .add_edge(START, "route_start")
    # reading → writing_task 由 Command 路由，不加静态边（否则 writing_task 会执行两次）
    .add_edge("writing_task", "evaluate_writing")
    .add_edge("evaluate_writing", "save_results")
    .add_edge("save_results", END)
    .compile(checkpointer=SqliteSaver.from_conn_string("./db.sqlite3"))
)
```

### 6.4 reading_session：interrupt() Validation Loop 实现

```python
from langgraph.types import interrupt, Command
from langgraph.config import get_stream_writer
from typing import Literal

def reading_session(state: TutorState) -> Command[Literal["writing_task"]]:
    # 重要：resume 时节点从头重新执行，interrupt() 之前只能做幂等操作
    db.upsert_reading_start(date.today())  # upsert，幂等安全

    while True:
        user_action = interrupt({
            "type": "awaiting_action",
            "article_full_text": state["today_article"].full_text,
            "highlight_indices": state["today_article"].highlight_indices,
            "user_level": state["user_profile"].level,
        })

        writer = get_stream_writer()

        if user_action["type"] == "explain_word":
            # interrupt() 之后执行，每次迭代只跑一次，安全
            result = explain_word(
                word=user_action["word"],
                context=user_action["context"],
                level=state["user_profile"].level,
            )
            writer({"type": "word_explanation", "result": result})

        elif user_action["type"] == "analyze_sentence":
            result = analyze_sentence(user_action["sentence"])
            writer({"type": "sentence_analysis", "result": result})

        elif user_action["type"] == "done_reading":
            break

    return Command(goto="writing_task")
```

**FastAPI SSE 统一入口：**

```python
@app.post("/api/lesson/action")
async def send_reading_action(action: dict):
    config = {"configurable": {"thread_id": date.today().isoformat()}}

    async def generate():
        async for chunk in graph.astream(
            Command(resume=action),   # 恢复 interrupt
            config=config,
            stream_mode="custom",     # 接收 stream_writer 数据
        ):
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

**幂等规则（节点 resume 时从头重新执行）：**
- `interrupt()` 之前：只用 `upsert`，不用 `insert`
- 副作用（工具调用结果）：放在 `interrupt()` 之后，每次迭代只跑一次

### 6.5 点词/析句走 LangGraph 的理由

```
用户点击 "migration"
→ reading_session 节点收到消息
→ LLM 已知 State：Article 原文 + UserProfile.level = 6
→ explain_word 工具自动携带这些上下文
→ 解释深度自动匹配用户水平，无需手动传参
```

---

## 7. DeepAgent Planner + Scout

```python
from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model

planner = create_deep_agent(
    model=init_chat_model("anthropic:claude-sonnet-4-6"),
    tools=[
        load_user_profile,    # 读取 SQLite UserProfile
        search_articles,      # Tavily API → 候选 URL 列表
        scrape_article,       # Scrapling（失败 fallback Playwright）
        highlight_key_paragraphs,  # Claude → 标注核心段落序号 + 识别文章逻辑类型
        generate_task,             # Claude → 写作任务（按 writing_mode）
        save_daily_lesson,         # SQLite → 写入 Article + WritingTask（Pydantic 边界）
    ],
    system_prompt="""
你是一个语言学习内容策划师。
根据用户的兴趣和职业目标，每天为他选择一篇真实的英文文章，
标注最核心的 3-5 个段落（用于前端高亮深读），识别文章底层逻辑类型，
并生成一个针对其目标的微型写作任务。
优先选择时效性强、与用户当前项目直接相关的内容。
    """,
    checkpointer=SqliteSaver.from_conn_string("./db.sqlite3"),  # 支持崩溃后恢复
)

# Planner thread_id 按日期，幂等重跑
PLANNER_CONFIG = {"configurable": {"thread_id": f"planner-{date.today()}"}}

# DeepAgent 内置 write_todos 自动规划步骤：
# 1. 读取用户画像和兴趣
# 2. 搜索 2-3 篇相关文章
# 3. 抓取最优文章完整正文，标注核心段落序号 + 识别逻辑类型
# 4. 生成配套写作任务
# 5. 存入数据库
```

### DeepAgent 可靠性：Pydantic 工具边界

不约束 LLM 的输出文本，约束工具签名。验证失败自动重试：

```python
class ArticleCreate(BaseModel):
    original_title: str
    source_url: HttpUrl
    full_text: str = Field(min_length=100)
    highlight_indices: list[int] = Field(min_length=3, max_length=5)
    article_logic: Literal["compare", "cause_effect", "argumentation"]
    topic_tags: list[str] = Field(min_length=1, max_length=5)

class WritingTaskCreate(BaseModel):
    mode: Literal["professional", "ielts_task1", "ielts_task2"]
    instruction: str = Field(min_length=50)
    min_words: int = Field(ge=50, le=250)

@tool
def save_daily_lesson(article: ArticleCreate, task: WritingTaskCreate) -> str:
    """Save today's article and writing task. Call this as the final step."""
    db.upsert_article(article)   # upsert，幂等
    db.upsert_task(task)
    return f"Saved: '{article.original_title}'"
```

`highlight_key_paragraphs` 用 `with_structured_output()` 强制结构化输出：

```python
@tool
def highlight_key_paragraphs(
    full_text: str, user_goal: str, interests: list[str]
) -> dict:
    """Identify 3-5 core paragraphs and article logic type for a language learner."""
    class HighlightResult(BaseModel):
        highlight_indices: list[int] = Field(
            description="0-based indices of 3-5 core paragraphs most relevant to user goal",
            min_length=3,
            max_length=5,
        )
        article_logic: Literal["compare", "cause_effect", "argumentation"] = Field(
            description="Underlying logical structure of the article"
        )

    paragraphs = full_text.split("\n\n")
    result = (
        llm.with_structured_output(HighlightResult)
        .invoke(HIGHLIGHT_PROMPT.format(
            paragraphs="\n\n".join(f"[{i}] {p}" for i, p in enumerate(paragraphs)),
            goal=user_goal,
            interests=", ".join(interests),
        ))
    )
    # 验证序号在有效范围内
    valid_indices = [i for i in result.highlight_indices if 0 <= i < len(paragraphs)]
    return {"highlight_indices": valid_indices, "article_logic": result.article_logic}
```

### Scrapling fallback 策略

```python
from scrapling import Scraper
from playwright.async_api import async_playwright

async def scrape_article(url: str) -> str:
    try:
        scraper = Scraper(auto_match=True)
        page = scraper.get(url)
        return page.get_best_text(auto_filter=True)
    except Exception:
        # fallback：Playwright 处理 JS 渲染页面
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(url)
            content = await page.inner_text("body")
            await browser.close()
            return content
```

---

## 8. FastAPI 路由

```python
# 慢循环 — Planner 触发
POST  /api/planner/run          # BackgroundTasks 异步启动 DeepAgent
GET   /api/planner/status       # 查询今日课程是否就绪

# 快循环 — 阅读
GET   /api/lesson/today         # 返回今日 Article + WritingTask

# 统一交互入口（点词/点句/完成阅读/答填空/提交写作）
# action.type: "explain_word" | "analyze_sentence" | "done_reading"
#            | "fill_blank_answer" | "submit_writing"
POST  /api/lesson/action        # → Command(resume=action) → LangGraph SSE 流式

# 用户画像
GET   /api/profile
PATCH /api/profile              # 自然语言更新兴趣

# BackgroundTasks 用法
@app.post("/api/planner/run")
async def run_planner(background_tasks: BackgroundTasks):
    background_tasks.add_task(planner.ainvoke, {
        "messages": [{"role": "user", "content": "为今天准备一节课"}]
    })
    return {"status": "started"}
```

---

## 9. Next.js 页面结构

```
app/
├── page.tsx                 # 入口：检查 profile → 重定向
├── onboarding/
│   └── page.tsx             # 首次使用：AI 对话建立 UserProfile
├── lesson/
│   └── page.tsx             # 主战场：复习 → 精读 → 写作
└── profile/
    └── page.tsx             # 查看/修改兴趣和目标
```

### /lesson 组件树

```
<LessonPage>
  ├── <ReviewGate>               // Step 1：有到期词时显示
  │   └── <FillBlankCard>        // 一道填空，答对推进 index
  │
  ├── <ArticleReader>            // Step 2：精读区
  │   ├── <FullArticle>          // 渲染完整原文，highlight_indices 对应段落高亮显示
  │   │   ├── <WordChip>         // 点击 → popover SSE 流式释义
  │   │   └── <SentenceBtn>      // 点击 → drawer SSE 流式句子分析
  │   └── <ReadingDoneBtn>
  │
  └── <WritingPanel>             // Step 3
      ├── <TaskInstruction>
      ├── <Textarea>
      ├── <WordCount>            // 实时字数
      └── <FeedbackView>         // SSE 流式展示批改结果
          ├── <ScoreBadge>
          ├── <ErrorList>        // 语法 + Chinglish 标注
          └── <RewriteCards>     // 2 个地道重写版本
```

### TypeScript 类型（镜像 Pydantic 模型）

```typescript
// types/index.ts
export type LessonPhase = 'review' | 'reading' | 'writing' | 'feedback'

export interface Article {
  id: number
  date: string
  source_url: string
  original_title: string
  full_text: string
  highlight_indices: number[]  // 核心段落序号（0-based），前端据此高亮渲染
  article_logic: 'compare' | 'cause_effect' | 'argumentation'
  topic_tags: string[]
}

export interface WritingTask {
  id: number
  article_id: number
  mode: 'professional' | 'ielts_task1' | 'ielts_task2'
  instruction: string
  min_words: number
}

export interface ChinglishFlag {
  original: string
  issue: 'word_choice' | 'sentence_structure' | 'logic_connector'
  explanation_zh: string
  native_alternative: string
}

export interface WritingFeedback {
  overall_score: number
  grammar_errors: { original: string; correction: string; explanation_zh: string }[]
  chinglish_flags: ChinglishFlag[]
  rewrite_suggestions: string[]
}

// LangGraph SSE 推送的数据块类型
export type SSEChunk =
  | { type: 'fill_blank'; question: string; word: string }
  | { type: 'word_explanation'; result: string }
  | { type: 'sentence_analysis'; result: string }
  | { type: 'feedback'; result: WritingFeedback }
```

### API 代理（Next.js → FastAPI，零 CORS 问题）

```typescript
// app/api/[...proxy]/route.ts
import { NextRequest } from 'next/server'

const BACKEND = process.env.BACKEND_URL ?? 'http://localhost:8000'

export async function GET(req: NextRequest, { params }: { params: { proxy: string[] } }) {
  const path = params.proxy.join('/')
  return fetch(`${BACKEND}/api/${path}`)
}

export async function POST(req: NextRequest, { params }: { params: { proxy: string[] } }) {
  const path = params.proxy.join('/')
  return fetch(`${BACKEND}/api/${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: await req.text(),
  })
}
```

前端所有请求打 `/api/*`，Next.js 透传到 FastAPI，不需要配置 CORS。

### SSE 客户端工具

```typescript
// lib/sse.ts
type Action =
  | { type: 'explain_word'; word: string; context: string }
  | { type: 'analyze_sentence'; sentence: string }
  | { type: 'done_reading' }
  | { type: 'fill_blank_answer'; answer: string; response_seconds: number }
  | { type: 'submit_writing'; text: string }

export async function sendAction(
  action: Action,
  onChunk: (chunk: SSEChunk) => void,
): Promise<void> {
  const res = await fetch('/api/lesson/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(action),
  })

  const reader = res.body!.getReader()
  const decoder = new TextDecoder()

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const lines = decoder.decode(value).split('\n')
    for (const line of lines) {
      if (line.startsWith('data: ') && !line.includes('[DONE]')) {
        onChunk(JSON.parse(line.slice(6)))
      }
    }
  }
}
```

### SWR Hooks

```typescript
// hooks/useLesson.ts
import useSWR from 'swr'
import type { Article, WritingTask } from '@/types'

const fetcher = (url: string) => fetch(url).then(r => r.json())

export function useTodayLesson() {
  return useSWR<{ article: Article; task: WritingTask }>('/api/lesson/today', fetcher)
}

export function usePlannerStatus() {
  // 每 3 秒轮询，直到课程就绪
  return useSWR<{ ready: boolean }>('/api/planner/status', fetcher, {
    refreshInterval: data => (data?.ready ? 0 : 3000),
  })
}
```

### useReducer 状态机（/lesson 页面）

```typescript
// app/lesson/reducer.ts
import type { LessonPhase, WritingFeedback } from '@/types'

interface LessonState {
  phase: LessonPhase
  popover: { word: string; explanation: string } | null
  drawer: { sentence: string; analysis: string } | null
  feedback: WritingFeedback | null
  isStreaming: boolean
}

type LessonAction =
  | { type: 'REVIEW_DONE' }
  | { type: 'WORD_CLICK'; word: string }
  | { type: 'WORD_EXPLAINED'; word: string; explanation: string }
  | { type: 'POPOVER_CLOSE' }
  | { type: 'SENTENCE_CLICK'; sentence: string }
  | { type: 'SENTENCE_ANALYZED'; analysis: string }
  | { type: 'READING_DONE' }
  | { type: 'WRITING_STREAM_START' }
  | { type: 'FEEDBACK_DONE'; feedback: WritingFeedback }

const init: LessonState = {
  phase: 'review',
  popover: null,
  drawer: null,
  feedback: null,
  isStreaming: false,
}

export function lessonReducer(state: LessonState, action: LessonAction): LessonState {
  switch (action.type) {
    case 'REVIEW_DONE':       return { ...state, phase: 'reading' }
    case 'WORD_CLICK':        return { ...state, isStreaming: true }
    case 'WORD_EXPLAINED':    return { ...state, isStreaming: false, popover: action }
    case 'POPOVER_CLOSE':     return { ...state, popover: null }
    case 'SENTENCE_ANALYZED': return { ...state, isStreaming: false, drawer: { ...state.drawer!, analysis: action.analysis } }
    case 'READING_DONE':      return { ...state, phase: 'writing', drawer: null, popover: null }
    case 'WRITING_STREAM_START': return { ...state, isStreaming: true }
    case 'FEEDBACK_DONE':     return { ...state, phase: 'feedback', isStreaming: false, feedback: action.feedback }
    default:                  return state
  }
}
```

### 关键组件：WordChip

```typescript
// components/WordChip.tsx
'use client'
import { sendAction } from '@/lib/sse'

interface Props {
  word: string
  context: string
  onExplained: (explanation: string) => void
}

export function WordChip({ word, context, onExplained }: Props) {
  const handleClick = async () => {
    let buffer = ''
    await sendAction(
      { type: 'explain_word', word, context },
      chunk => {
        if (chunk.type === 'word_explanation') {
          buffer += chunk.result
          onExplained(buffer)  // 逐步更新 popover
        }
      },
    )
  }

  return (
    <span
      className="cursor-pointer underline decoration-dotted hover:bg-yellow-100"
      onClick={handleClick}
    >
      {word}
    </span>
  )
}
```

### 环境变量

```bash
# frontend/.env.local
BACKEND_URL=http://localhost:8000

# backend/.env
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...
```

---

## 10. 项目结构（uv 管理）

```
language-teacher/
├── pyproject.toml           # uv 管理所有 Python 依赖 + ruff/mypy 配置
├── Taskfile.yml             # 统一命令入口
├── .pre-commit-config.yaml  # Git hooks 配置
├── .env                     # ANTHROPIC_API_KEY, TAVILY_API_KEY
├── db.sqlite3               # 本地数据库 + LangGraph checkpoints
│
├── backend/
│   ├── main.py              # FastAPI app 入口
│   ├── tutor/
│   │   ├── graph.py         # LangGraph Tutor StateGraph
│   │   ├── nodes.py         # 各节点函数
│   │   └── tools.py         # explain_word, analyze_sentence 等
│   ├── planner/
│   │   ├── agent.py         # create_deep_agent 初始化
│   │   └── tools.py         # search, scrape, compress, generate
│   ├── models.py            # Pydantic 数据模型（权威类型定义）
│   ├── database.py          # SQLite CRUD
│   └── fsrs_engine.py       # py-fsrs 封装
│
└── frontend/                # Next.js 项目
    ├── package.json         # lint-staged, husky 配置
    ├── eslint.config.mjs
    ├── .prettierrc
    ├── tsconfig.json        # strict: true
    ├── types/
    │   └── api.ts           # ⚡ 自动生成，勿手改（openapi-typescript 产出）
    ├── lib/
    │   └── sse.ts           # SSE 客户端工具
    ├── hooks/
    │   └── useLesson.ts     # SWR hooks
    └── app/
        ├── api/[...proxy]/route.ts  # FastAPI 代理，消除 CORS
        ├── page.tsx
        ├── lesson/
        │   ├── page.tsx
        │   └── reducer.ts
        ├── onboarding/page.tsx
        └── profile/page.tsx
```

---

## 11. 写作批改：Prompt 策略与结构化输出

### Prompt 策略（两遍扫描）

```python
FEEDBACK_PROMPT = """
You are a native English editor reviewing writing from a Chinese professional.

Source article topic: {article_topic}
Writer's goal: {user_goal}
Writer's level: {level}/10

PASS 1 — Grammar: Find objective errors (tense, agreement, articles).
PASS 2 — Native fluency: Find phrases where Chinese L1 is showing through.
  Ask: "Would a native speaker in this professional context phrase it this way?"
  Focus on: verb weakening (用 "have" 替代强动词), logic connectors (中式衔接词),
            sentence rhythm (头重脚轻结构).
  Do NOT flag correct-but-non-native as grammar errors.

Return valid JSON matching the schema exactly. No prose outside JSON.
"""
```

### with_structured_output() + 重试（不用 instructor）

```python
def run_feedback(user_text: str, task: WritingTask) -> WritingFeedback:
    structured_llm = llm.with_structured_output(WritingFeedback, include_raw=True)
    prompt = build_feedback_prompt(user_text, task)

    for attempt in range(3):
        result = structured_llm.invoke(prompt)
        if result["parsed"] is not None:
            return result["parsed"]
        # 失败时 log 原始输出方便调试
        logger.warning(f"Attempt {attempt+1} failed: {result['raw']}")

    raise ValueError("Feedback generation failed after 3 attempts")
```

`include_raw=True`：验证失败时可拿到原始输出，方便 debug。

---

## 12. py-fsrs 集成

### FSRS vs SM-2

SM-2 追踪「间隔」和「易记系数」；FSRS 追踪两个心理学变量：
- **Stability（稳定性）**：记忆能撑多久不忘
- **Retrievability（可提取性）**：此刻能想起来的概率

在遗忘临界点附近调度精度远优于 SM-2。

### Rating 映射（答题时长决定难易）

```python
from fsrs import FSRS, Card, Rating

def map_answer_to_rating(is_correct: bool, response_seconds: float) -> Rating:
    if not is_correct:
        return Rating.Again
    if response_seconds > 15:
        return Rating.Hard
    elif response_seconds > 5:
        return Rating.Good
    else:
        return Rating.Easy
```

### Card SQLite 序列化

```python
# 保存到 fsrs_state 字段（JSON）
def serialize_card(card: Card) -> dict:
    return {
        "due": card.due.isoformat(),
        "stability": card.stability,
        "difficulty": card.difficulty,
        "reps": card.reps,
        "lapses": card.lapses,
        "state": card.state.value,   # 0=New 1=Learning 2=Review 3=Relearning
        "last_review": card.last_review.isoformat() if card.last_review else None,
    }

# 从数据库恢复
def deserialize_card(data: dict) -> Card:
    return Card(**data)
```

---

## 13. 关键技术决策记录

| 决策点 | 选择 | 理由 |
|---|---|---|
| 学习模式 | 读写飞轮，非 Duolingo | 成人专业学习者需要真实输出场景 |
| 爬虫 | Scrapling + Playwright fallback | 本地免费，覆盖静态和动态页面 |
| 流式传输 | SSE | 单向流，Next.js 原生支持，比 WebSocket 简单 |
| Session 恢复 | thread_id = 日期字符串 | 每天一个 checkpoint，天然支持中断恢复 |
| 词汇算法 | py-fsrs | 比 SM-2 更准确的现代间隔重复算法 |
| 点词/析句 | 走 LangGraph Tutor 节点 | 自动携带文章上下文和用户 level，无需手动传参 |
| Planner 触发 | FastAPI BackgroundTasks | 统一后端入口，异步不阻塞 |
| 数据库 | SQLite | 本地零配置，兼作 LangGraph SqliteSaver |
| 结构化输出 | `with_structured_output()` 统一使用 | 保持 LangChain 生态一体，不引入 instructor |
| 复杂模型重试 | `include_raw=True` + 手动 3 次循环 | 验证失败可 log 原始输出，方便 debug |
| reading_session | `interrupt()` Validation Loop | 多次点词/点句在同一节点内循环等待 |
| interrupt 幂等 | 副作用放在 `interrupt()` 之后 | 节点 resume 时从头重执行，避免重复写库 |
| DeepAgent 可靠性 | Pydantic 工具签名作为边界 | 验证失败 → ToolMessage → LLM 自动重试 |
| FSRS Rating | 答题时长映射 Again/Hard/Good/Easy | 比纯对错判断更精准反映记忆难度 |
| 前端类型来源 | openapi-typescript 自动生成 | 消除手动维护 types/index.ts 的漂移风险 |
| TS Lint | ESLint + Prettier | Biome 生态不够成熟，ESLint 插件更完整 |
| Python Lint | Ruff | 替代 Black+isort+flake8，极快 |
| mypy 严格度 | 宽松（ignore_missing_imports） | LangGraph/DeepAgents stub 不完整，全量 strict 噪音过多 |
| Git hooks | pre-commit + husky + lint-staged | lint-staged 只检查改动文件，提交不卡顿 |
| Commit 规范 | commitlint（conventional commits） | 与 git-workflow.md 保持一致 |
| 观测平台 | LangSmith | 三行环境变量，全链路 trace 自动上报 |
| Onboarding Agent | DeepAgent（独立） | 一次性任务，自主规划对话节奏，与 Tutor 共享 SQLite |
| 精读方案 | 全文 + 高亮段落 | 保留原文完整逻辑链；AI 标注 3-5 个核心段落，用户自主控制阅读深度 |

---

## 14. 质量守卫配置

### 工具链总览

| 工具 | 层 | 作用 |
|---|---|---|
| **Ruff** | Python | lint + format |
| **mypy（宽松）** | Python | 类型检查，放行第三方缺失 stub |
| **ESLint + Prettier** | TypeScript | lint + format |
| **tsc --noEmit** | TypeScript | 编译期类型检查 |
| **openapi-typescript** | 跨栈 | Pydantic → TS 类型自动同步 |
| **lint-staged** | Git | 只检查改动文件 |
| **commitlint** | Git | 强制 conventional commits |
| **Taskfile** | 全局 | 统一命令入口 |

### Taskfile.yml

```yaml
version: '3'

tasks:
  dev:backend:
    cmd: uv run uvicorn backend.main:app --reload --port 8000

  dev:frontend:
    cmd: cd frontend && npm run dev

  generate-types:
    desc: "Pydantic 模型改动后手动执行，同步 TS 类型"
    cmds:
      - uv run uvicorn backend.main:app --port 8001 &
      - sleep 2
      - npx openapi-typescript http://localhost:8001/openapi.json -o frontend/types/api.ts
      - kill %1

  check:python:
    cmds:
      - uv run ruff check backend/
      - uv run ruff format --check backend/
      - uv run mypy backend/

  check:frontend:
    cmds:
      - cd frontend && npx eslint .
      - cd frontend && npx tsc --noEmit

  check:
    cmds: [task: check:python, task: check:frontend]

  fix:
    cmds:
      - uv run ruff check --fix backend/
      - uv run ruff format backend/
      - cd frontend && npx eslint . --fix
      - cd frontend && npx prettier --write .

  install-hooks:
    cmds:
      - uv run pre-commit install
      - uv run pre-commit install --hook-type commit-msg
      - cd frontend && npx husky init
      - echo "npx lint-staged" > frontend/.husky/pre-commit
```

### pyproject.toml（完整配置）

```toml
[project]
name = "dynamiclingo-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    # LangChain 核心（LTS 1.0）
    "langchain>=1.0,<2.0",
    "langchain-core>=1.0,<2.0",
    "langsmith>=0.3.4",             # 0.3.4+ required for langsmith[pytest] plugin

    # 编排层
    "langgraph>=1.0,<2.0",
    "langgraph-checkpoint-sqlite",  # SqliteSaver
    "deepagents",                   # 内部已捆绑 langgraph，use latest

    # 模型 provider
    "langchain-anthropic",

    # 工具集成（专用包，keep latest）
    "langchain-tavily",             # 不用 langchain-community 的 Tavily

    # Backend
    "fastapi[standard]",
    "uvicorn[standard]",

    # 爬虫
    "scrapling",
    "playwright",

    # 间隔重复
    "py-fsrs",

    # 工具
    "python-dotenv",
]

[project.optional-dependencies]
dev = [
    "langsmith[pytest]",    # LangSmith eval + pytest plugin (requires langsmith>=0.3.4)
    "pytest",
    "pytest-asyncio",
    "pre-commit",
    "mypy",
    "ruff",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]   # pycodestyle + pyflakes + isort + pyupgrade

[tool.mypy]
python_version = "3.12"
ignore_missing_imports = true     # LangGraph/DeepAgents stub 不完整
disallow_untyped_defs = false     # 不强制所有函数注解
warn_return_any = false
check_untyped_defs = true
exclude = ["frontend/", ".venv/"]

[[tool.mypy.overrides]]
module = "backend.models"         # 数据模型层强制完整注解
disallow_untyped_defs = true
```

### .pre-commit-config.yaml

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: local
    hooks:
      - id: mypy
        name: mypy
        entry: uv run mypy backend/
        language: system
        pass_filenames: false
        types: [python]

      - id: tsc
        name: tsc
        entry: bash -c 'cd frontend && npx tsc --noEmit'
        language: system
        pass_filenames: false
        types: [ts, tsx]

      - id: openapi-drift
        name: Warn if models.py changed without regenerating types
        entry: bash -c 'git diff --cached --name-only | grep -q "backend/models.py" && echo "⚠️  models.py changed — run: task generate-types" && exit 1 || exit 0'
        language: system
        pass_filenames: false

  - repo: https://github.com/commitizen-tools/commitizen
    rev: v3.13.0
    hooks:
      - id: commitizen
        stages: [commit-msg]
```

### ESLint + Prettier（frontend）

```js
// frontend/eslint.config.mjs
import nextPlugin from '@next/eslint-plugin-next'
import reactHooks from 'eslint-plugin-react-hooks'
import tsParser from '@typescript-eslint/parser'

export default [
  { files: ['**/*.{ts,tsx}'], languageOptions: { parser: tsParser } },
  { plugins: { '@next/next': nextPlugin }, rules: nextPlugin.configs.recommended.rules },
  { plugins: { 'react-hooks': reactHooks }, rules: reactHooks.configs.recommended.rules },
]
```

```json
// frontend/.prettierrc
{ "semi": false, "singleQuote": true, "trailingComma": "all", "printWidth": 100 }
```

```json
// frontend/package.json（lint-staged 配置）
{
  "lint-staged": {
    "*.{ts,tsx}": ["eslint --fix", "prettier --write"],
    "*.{json,css,md}": ["prettier --write"]
  }
}
```

### Git 提交触发链路

```
git commit
  → husky → lint-staged（只检查改动的 ts/tsx 文件）
  → pre-commit → ruff + mypy + tsc + openapi-drift 警告
  → commitlint → 校验 commit message 格式（feat/fix/chore 等）
```

### 一次性初始化

```bash
# Python 质量工具
uv add --dev pre-commit mypy ruff
task install-hooks

# 前端质量工具
cd frontend && npm i -D \
  eslint prettier \
  @next/eslint-plugin-next \
  eslint-plugin-react-hooks \
  @typescript-eslint/parser \
  lint-staged husky
```

---

## 15. LangSmith 观测配置

```bash
# .env — 三行开启全链路追踪
LANGSMITH_TRACING=true           # 新版变量名（等效旧版 LANGCHAIN_TRACING_V2=true）
LANGSMITH_API_KEY=ls-...
LANGSMITH_PROJECT="dynamiclingo"
```

自动追踪内容：
- DeepAgent Planner 每步（`write_todos` → 搜索 → 抓取 → 压缩 → 生成）
- LangGraph 每个节点的输入输出和耗时
- `with_structured_output()` 失败时的原始 LLM 响应
- Claude API token 用量和费用累计

无需改任何代码，所有 LangChain/LangGraph 调用自动上报。

---

## 16. Onboarding 流程

**设计原则：** Onboarding 是一次性的自主对话任务，DeepAgent 天然胜任，无需手写 LangGraph 节点。

```python
# backend/onboarding/agent.py
from langgraph.checkpoint.sqlite import SqliteSaver

onboarding_agent = create_deep_agent(
    model=init_chat_model("anthropic:claude-sonnet-4-6"),
    tools=[save_user_profile],
    checkpointer=SqliteSaver.from_conn_string("./db.sqlite3"),  # 必须：多轮对话记忆
    system_prompt="""
你是一位温和的语言学习顾问，正在为用户做入学评估。
通过自然对话（不超过 6 轮）收集以下信息：

1. goal（学习目标）：具体的应用场景，追问直到足够具体
   例："读英文文档" → "读哪类文档？" → "TypeScript 官方文档和 RFC"
2. interests（兴趣关键词）：3-5 个，用于指导文章抓取
3. level（英文水平 1-10）：通过对话隐式判断，不要直接问"你几级"
   观察用词复杂度、是否主动用英文、语法错误频率
4. bandwidth_minutes（每日时间）：询问碎片时间，换算成分钟
5. writing_mode：职场输出 / 雅思备考 / 两者都要

收集完毕后调用 save_user_profile 工具，并告知用户今日课程即将生成。
对话语气：专业、温和、简洁，不要过度热情。
    """,
)

# thread_id 固定，单用户一次性对话
ONBOARDING_CONFIG = {"configurable": {"thread_id": "onboarding"}}
```

**FastAPI 端点：**

```python
POST /api/onboarding/message   # 用户发消息 → SSE 流式返回 Agent 回复
GET  /api/onboarding/status    # 检查 UserProfile 是否已保存
```

**前端流程：**

```
/onboarding 页面
  → 聊天 UI（消息列表 + 输入框）
  → SSE 流式展示 Agent 回复
  → 轮询 /api/onboarding/status
  → UserProfile 写入 SQLite 后
  → 自动触发 POST /api/planner/run（生成今日课程）
  → 跳转到 /lesson
```

**与 Tutor 的关系：**

```
Onboarding Agent（DeepAgent，一次性）
    ↓ save_user_profile() → SQLite
每日 Planner（DeepAgent，每日触发）
    ↓ 读取 UserProfile → 生成课程
每日 Tutor（LangGraph，每日循环）
    ↓ 读取课程 → 精读 + 写作
```

三个 Agent 共用同一个 `db.sqlite3`，thread_id 不同，namespace 天然隔离：

| Agent | thread_id | checkpointer |
|---|---|---|
| Onboarding | `"onboarding"` | 必须（多轮对话记忆） |
| Planner | `f"planner-{date.today()}"` | 建议加（支持崩溃恢复） |
| Tutor | `date.today().isoformat()` | 必须（interrupt 恢复）|

**FastAPI 启动时一次性初始化 checkpointer 表：**

```python
# backend/main.py
from contextlib import asynccontextmanager
from langgraph.checkpoint.sqlite import SqliteSaver

@asynccontextmanager
async def lifespan(app: FastAPI):
    with SqliteSaver.from_conn_string("./db.sqlite3") as cp:
        cp.setup()  # 建表，幂等，重复调用安全
    yield

app = FastAPI(lifespan=lifespan)
```

---

## 17. highlight_key_paragraphs Prompt

**核心定位：不改写原文，只标注。** 返回段落序号和文章逻辑类型，前端据此高亮渲染。

```python
HIGHLIGHT_PROMPT = """
You are a language learning content curator for professional English learners.

Given an article split into numbered paragraphs, identify:
1. The 3-5 most valuable paragraphs for deep reading (highlight_indices)
2. The article's underlying logical structure (article_logic)

PARAGRAPHS:
{paragraphs}

LEARNER PROFILE:
- Goal: {goal}
- Interests: {interests}

SELECTION CRITERIA for highlight_indices:
- Paragraphs that directly serve the learner's goal
- Paragraphs with the highest density of professional vocabulary or advanced sentence structures
- The paragraph that contains the core argument or key insight
- Paragraphs with strong collocations worth learning
- Avoid: introductory boilerplate, conclusion summaries, promotional content

ARTICLE LOGIC DEFINITIONS:
- compare: article compares two or more approaches, technologies, or viewpoints
- cause_effect: article explains why something happened or what results from an action
- argumentation: article makes a claim and defends it with evidence

Return ONLY the structured output. Do not explain your choices.
"""
```
