---
description: LangGraph 节点、图、checkpointer、interrupt 编写规则
paths:
  - "backend/tutor/**/*.py"
  - "backend/general/**/*.py"
  - "backend/planner/**/*.py"
  - "backend/reflect/**/*.py"
  - "backend/onboarding/**/*.py"
---

# LangGraph 编写规则

## 写代码前必须 invoke 的 Skills

| 场景 | 必须 invoke |
|------|------------|
| 选择框架前 | `langchain-skills:framework-selection` |
| 写任何 LangGraph 节点/图 | `langchain-skills:langgraph-fundamentals` |
| 写 `interrupt()` / `Command(resume=...)` | `langchain-skills:langgraph-human-in-the-loop` |
| 写 checkpointer / thread_id / Store | `langchain-skills:langgraph-persistence` |
| 安装或升级依赖 | `langchain-skills:langchain-dependencies` |

## 踩坑规则（从项目实践中提炼）

### interrupt() 幂等性
节点 resume 时**从顶部重跑**，`interrupt()` 前只能用 **upsert**，不能用 **insert**。
否则 resume 时会重复插入数据。

### Command 路由 vs 静态边互斥
用了 `Command(goto="X")` 就**不能**再 `add_edge(A, "X")`。
两者同时存在会导致节点 X 执行两次。

### `while True: interrupt()` 模式
`reading_session` 节点专用写法：每次 resume 节点重跑，`interrupt()` 在循环顶部等待用户输入。

### RetryPolicy 按需添加
只有 `reading` 和 `evaluate_writing` 节点需要 RetryPolicy，其他节点不加。
过度添加会掩盖真实错误。

### Checkpointer 单例
从 `app.state.checkpointer` 取，**禁止**在模块内单独调用 `from_conn_string()`。
否则会创建多个连接，导致状态不一致。

### Thread ID 约定
| Agent | Thread ID 格式 |
|-------|---------------|
| Tutor | `date.today().isoformat()` |
| Planner | `f"planner-{date.today().isoformat()}"` |
| Onboarding | `"onboarding"`（固定字符串） |
