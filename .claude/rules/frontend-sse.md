---
description: Next.js 前端 SSE streaming、代理架构、类型生成规则
paths:
  - "frontend/**/*.ts"
  - "frontend/**/*.tsx"
---

# 前端 SSE 与架构规则

## SSE cleanup 必须做

`useEffect` 里启动的 SSE stream **必须**在 cleanup 函数中 abort：

```typescript
useEffect(() => {
  const controller = new AbortController();
  startLesson(lessonId, controller.signal);

  return () => controller.abort(); // 必须！
}, [lessonId]);
```

忘记 cleanup → 切路由时 stream 泄漏，持续消耗 token 和内存。

## 代理透传架构

前端**不直接**调 FastAPI，统一走 Next.js 代理：

```
前端 → /api/... → app/api/[...proxy]/route.ts → FastAPI :8000
```

好处：无 CORS 问题，不暴露后端地址。

## `frontend/types/api.ts` 禁止手动编辑

由 `task generate-types` 自动生成，手动改会被覆盖。
需要修改类型 → 改 `backend/models.py` 然后运行 `task generate-types`。

## SWR vs SSE 选择

| 场景 | 用法 |
|------|------|
| 静态数据（一次性加载） | SWR |
| 实时流式交互 | `lib/sse.ts`（`startLesson`、`sendOnboardingMessage`） |

不要对流式接口用 SWR，SWR 不支持 streaming 响应。
