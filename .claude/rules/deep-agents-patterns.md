---
description: Deep Agent（create_deep_agent）、多 agent 编排、RAG 向量检索编写规则
paths:
  - "backend/planner/**/*.py"
  - "backend/reflect/**/*.py"
  - "backend/onboarding/**/*.py"
  - "backend/general/researcher.py"
  - "backend/general/reflect.py"
  - "backend/general/onboarding.py"
  - "backend/memory.py"
---

# Deep Agents 编写规则

## 写代码前必须 invoke 的 Skills

| 场景 | 必须 invoke |
|------|------------|
| 写 `create_deep_agent()` | `langchain-skills:deep-agents-core` |
| 写多 agent 编排 / subagent | `langchain-skills:deep-agents-orchestration` |
| 写 `with_structured_output` / middleware | `langchain-skills:langchain-middleware` |
| 写 RAG / 向量检索（memory.py） | `langchain-skills:langchain-rag` |
| 安装或升级依赖 | `langchain-skills:langchain-dependencies` |

## 踩坑规则（从项目实践中提炼）

### 系统提示：写目标，不写步骤
Prose 描述目标，**不要用编号列表**。
原因：编号列表会与 `write_todos` 中间件冲突，导致 agent 行为混乱。

### 工具签名用 Pydantic 类型
```python
# 正确
def save_daily_lesson(article: ArticleCreate, lesson_id: int) -> dict: ...

# 错误
def save_daily_lesson(article_json: str) -> dict: ...
```
传 JSON 字符串会导致模型输出包含 markdown fence 时解析失败。

### 结构化输出用 `with_structured_output()`
**禁止** `json.loads(response.content)`，模型输出可能含 markdown fence（```json ... ```）导致解析失败。
改用：
```python
chain = llm.with_structured_output(MySchema)
result = await chain.ainvoke(messages)
```

### Singleton 模式
```python
# 正确：缓存实例，checkpointer 作为参数
def get_planner(checkpointer) -> CompiledGraph:
    ...

# 错误：每次调用都创建新实例
def create_planner() -> CompiledGraph:
    ...
```

### 工具返回格式统一
所有工具统一返回：
```python
{
    "status": "success" | "error",
    "summary": "...",
    "next_actions": [...],
    "data": ...
}
```
Agent 只检查 `status` 字段，其余字段用于人类调试。
