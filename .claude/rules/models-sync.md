---
description: models.py 与 frontend/types/api.ts 同步规则，防止前后端类型漂移
paths:
  - "backend/models.py"
  - "frontend/types/api.ts"
---

# Models 同步规则

## 改 models.py 后必须执行

```bash
task generate-types
```

这个命令把 Pydantic models 转成 `frontend/types/api.ts`，前后端类型自动保持同步。

## `frontend/types/api.ts` 禁止手动编辑

这是**自动生成文件**，手动改会在下次 `task generate-types` 时被覆盖，改了等于白改。

## pre-commit hook 会自动检查

`openapi-drift` hook 在每次 commit 前检查两边是否同步。
如果 hook 报错，说明你忘跑 `task generate-types` 了。

## 正确提交顺序

1. 编辑 `backend/models.py`
2. 运行 `task generate-types`
3. `git add backend/models.py frontend/types/api.ts`
4. `git commit`

不要只提交 `models.py` 而不提交 `frontend/types/api.ts`，否则 CI 会失败。
