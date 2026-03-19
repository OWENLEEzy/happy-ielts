# PRD: DynamicLingo — 动态 AI 读写语言导师

## Problem Statement

成年专业学习者（开发者、出海业务人员、考雅思者）有明确的英语学习动机，但传统教材（新概念、雅思真题、Duolingo）与他们的真实工作场景严重脱节：背的词用不上，做的题和实际工作无关，导致动力衰减、难以坚持。

核心问题是：**学习内容与真实需求脱节，输出环节缺失，没有形成认知闭环。**

## Solution

DynamicLingo 是一个本地运行的 AI 读写飞轮（Read-Write Flywheel），四层体验环环相扣：

1. **每日自动抓取**用户兴趣领域的真实英文文章（技术博客、出海营销案例等）
2. **全文沉浸阅读**：前端渲染完整原文，AI 仅用高亮标注最核心的 3-5 段，用户扫读全篇、在高亮处深读——保留完整逻辑链，不破坏上下文
3. **场景同化写作**：根据文章的底层逻辑（对比 / 因果 / 论证）动态生成任务，写作从阅读材料中自然生长，训练核心表达逻辑
4. **单点突破批改**：AI 每次只抓 1-2 个最严重的核心问题（致命语法或 Chinglish），配情绪抚慰和针对性重写建议，每天学透一个重难点
5. **渐进式搭配复习**：考察词汇在真实语境中的搭配与用法（Collocation & Chunk），答错触发"提示流"（词性/搭配 → 首字母 → 揭晓答案 + 解释用法差异），无挫败感完成关卡

整个系统为**个人本地使用**，零部署成本，15-25 分钟完成每日完整闭环。

## User Stories

### 破冰与画像

1. 作为新用户，我想通过与 AI 的自然对话完成初始配置，而不是填写枯燥的表单，这样我能快速感受到产品的智能。
2. 作为用户，我想告诉系统我的具体学习目标（如"无障碍阅读英文技术文档"），这样内容抓取和写作任务都围绕这个目标生成。
3. 作为用户，我想添加多个兴趣关键词（如"TypeScript 开发"、"医美出海营销"），这样每天的文章来自我真正关心的领域。
4. 作为用户，我想设置每日学习时长偏好（15 分钟 / 25 分钟），这样系统会控制每日内容量。
5. 作为用户，我想选择写作模式（职场流 / 雅思流 / 两者交替），这样写作任务匹配我的终极目标。
6. 作为用户，我想通过自然语言随时更新兴趣（"我最近接手了医美项目，多抓这方面的文章"），这样系统能动态调整抓取方向。

### 内容抓取与生成（后台）

7. 作为用户，我希望系统每天自动抓取符合我兴趣的最新英文文章，这样我不需要手动找材料。
8. 作为用户，我希望抓取结果只保留核心正文，剔除广告和侧边栏，这样阅读体验干净。
9. 作为用户，我希望系统存储完整原文正文，并由 AI 标注最核心的 3-5 个段落索引，这样前端可以渲染全文并用高亮区分深读区域。
10. 作为用户，我希望能看到文章的原始来源 URL 和完整标题，这样我可以选择去读全文。
11. 作为用户，我希望每日内容在我打开 App 之前就已准备好，这样打开即用，零等待。
12. 作为用户，如果某天抓取失败，我希望系统有降级机制（使用昨天的文章或备用内容），不影响学习连续性。

### 精读体验

13. 作为用户，我想在阅读界面看到完整原文，AI 高亮的 3-5 个核心段落视觉上更突出，其余段落正常显示可自由扫读。
14. 作为用户，我想在任意位置（高亮段或非高亮段）点击单词，立刻弹出 AI 结合当前上下文的精准解释，而不是字典的多个无关义项。
15. 作为用户，我想点击任意长难句，AI 用颜色或层级结构帮我拆解主谓宾和从句，降低理解负担。
16. 作为用户，我点击查询的每个词都应该自动记录到生词本，这样我不需要手动添加。
17. 作为用户，我想随时看到文章的标签（如"TypeScript / 架构 / Supabase"），了解今天的学习主题。
18. 作为用户，完成精读后，系统应该自动无缝衔接写作任务，不需要我额外操作。

### 写作任务——职场流

19. 作为职场用户，AI 分析完文章底层逻辑后，我希望收到与该逻辑匹配的职场任务：对比类文章 → 邮件比较两个方案并推荐；因果类文章 → 汇报一个问题的根因和解决路径；论证类文章 → 写一段说服老板的段落。
20. 作为职场用户，我希望写作指令直接复用文章中出现的真实名词（框架名、产品名、场景名），这样我用真实词汇写真实场景，而非凭空造句。
21. 作为职场用户，我希望有字数下限要求（如最少 50 字），督促我充分表达。

### 写作任务——雅思流

22. 作为雅思备考用户，对比类文章 → 我想收到"对比分析"写作任务，练习让步论证结构（While A...，B is more effective because...）。
23. 作为雅思备考用户，论点类文章 → 我想收到"立场论证"任务（To what extent do you agree？），争议点从文章真实内容中提取，而非通识题目。
24. 作为雅思备考用户，我希望写作指令包含字数要求（至少 150 字），并在任务描述中提示应使用的逻辑连接词或段落结构。
25. 作为雅思备考用户，我希望在熟悉的业务语境下练习雅思逻辑框架，而不是面对完全陌生的话题无从下手。

### AI 批改与反馈（单点突破）

26. 作为用户，提交写作后，AI 只指出 1-2 个最严重的核心问题（致命语法错误或严重 Chinglish），忽略不影响理解的小瑕疵，这样我不被满屏红线压垮。
27. 作为用户，批改结果应包含：问题定位（原句高亮）、问题解释（为什么不地道）、1 个针对性重写示范——简洁聚焦，不超过 3 条信息。
28. 作为用户，AI 批改语气应像一位鼓励式编辑：先肯定写得好的地方，再单刀直入指出核心问题，最后给出明确的改进示范。
29. 作为用户，被批改的核心词或句式应自动进入生词本，我不需要手动整理。
30. 作为用户，批改完成后我可以修改写作重新提交，在即时反馈下进行刻意练习。

### 每日复习关卡（渐进式搭配引导）

33. 作为用户，每天打开 App，如果有到期复习词汇，系统先呈现至多 3 道语境填空题，考察词汇在真实句子中的搭配与用法（Collocation），而非单纯拼写。
34. 作为用户，填空题的句子来自词汇的原始上下文（读文时的原句或写作被纠正的例句），这样复习有真实语感。
35. 作为用户，答错时系统依次给予渐进式提示：第一次错 → 词性/典型搭配提示；第二次错 → 首字母提示；第三次错 → 直接揭晓答案并解释用法差异（如 leverage vs. use 的语体差异），保证无挫败感完成关卡。
36. 作为用户，无论最终是自答还是经提示答出，都算通过该词关卡并解锁今日内容；但自答正确的词 py-fsrs 稳定性（stability）提升更多，经提示才答出的词间隔缩短，下次尽早复习。
37. 作为用户，我可以查看生词本，看到每个词的来源文章、原句、当前熟练度和下次复习日期。
38. 作为用户，如果没有到期复习词汇，直接进入今日精读，不浪费时间。

### 进度与历史

39. 作为用户，我想看到累计学习天数（学习连续记录），了解自己的坚持情况。
40. 作为用户，我想查看历史文章列表和对应的写作记录，回顾学过的内容。
41. 作为用户，我想看到生词本的增长曲线，感知词汇积累的进步。

## Implementation Decisions

### 整体架构：双循环分离

- **慢循环**（后台，每日手动触发一次）：DeepAgent Planner → Scout 爬取 → 存储全文 + AI 标注高亮段落序号 + 识别文章逻辑类型 → 生成写作任务 → 写入 SQLite
- **快循环**（前台，用户打开 App 触发）：Next.js UI ↔ FastAPI SSE ↔ LangGraph Tutor Graph ↔ SQLite
- 两循环通过 SQLite 解耦：慢循环生产内容，快循环消费内容

### 技术栈

| 层 | 选型 |
|----|------|
| 前端 | Next.js 14 + TypeScript (localhost:3000) |
| 后端 API | FastAPI + Uvicorn (localhost:8000) |
| Agent 编排 | LangGraph + DeepAgents (`create_deep_agent`) |
| LLM | Claude Sonnet (claude-sonnet-4-6) |
| 网页抓取 | Scrapling（本地，无外部依赖） |
| 搜索 API | Tavily（提供初始 URL 种子） |
| 数据库 | SQLite（`SqliteSaver` 作为 LangGraph Checkpointer） |
| 部署 | 纯本地，无需云部署 |

### 数据模型（核心 5 张表）

- **UserProfile**：goal, interests[], level(1-10), bandwidth_minutes, writing_mode
- **Article**：id, date, source_url, original_title, full_text(完整原文), highlight_indices(list[int], AI 标注的核心段落序号), article_logic(compare/cause_effect/argumentation), topic_tags[]
- **WritingTask**：id, article_id, mode(professional/ielts), instruction, min_words, logic_hint(提示应使用的逻辑结构或连接词)
- **WritingSubmission**：id, task_id, user_text, focus_issue(最严重的 1-2 个问题), rewrite_suggestion(针对性重写示范), encouragement(鼓励式开场白)
- **VocabItem**：id, word, context_sentence, source(reading_click/writing_error), next_review, fsrs_state(dict, py-fsrs Card 完整序列化状态)

### DeepAgent Planner 工具集

- `search_web(query)` — Tavily 搜索，获取目标 URL
- `scrape_article(url)` — Scrapling 抓取正文
- `highlight_key_paragraphs(full_text, user_goal, interests)` — Claude 返回核心段落的序号列表（不改写文本）及文章底层逻辑类型
- `generate_writing_task(article, profile)` — 生成写作指令（Pydantic 输出）
- `write_todos()` — DeepAgents 内置，规划今日抓取任务序列

### Onboarding Agent 设计（混合模式）

Onboarding 是一次性、需要自主规划对话节奏的任务，由 **DeepAgent** 主导前三个阶段，**结构化 UI 卡片**接管后两个阶段：

| Phase | 内容 | 形式 | 理由 |
|-------|------|------|------|
| 1 目标锚定 | goal | DeepAgent 对话（追问直到足够具体） | 需要挖掘细节，开放式 |
| 2 兴趣画像 | interests[] | 对话采集 + tag 确认卡 | 对话灵活，UI 确认准确 |
| 3 水平测定 | level | 用户写 2-3 句英文 → AI 隐式评估 | 必须真实产出，不问"你几级" |
| 4 时间带宽 | bandwidth_minutes | UI 选择卡（15分钟 / 25分钟 / 不确定） | 有限选项，点击比对话快 |
| 5 写作模式 | writing_mode | UI 选择卡（职场流 / 雅思流 / 两者） | 同上 |

```python
onboarding_agent = create_deep_agent(
    model=init_chat_model("anthropic:claude-sonnet-4-6"),
    tools=[save_partial_profile],  # 阶段性保存，前端读取后渲染 UI 卡片
    system_prompt="""
你是一位温和的语言学习顾问，正在为用户做入学评估。
通过自然对话（不超过 6 轮）完成以下收集：
1. goal：具体应用场景，追问直到足够具体
2. interests：3-5 个关键词，用于指导文章抓取
3. level：通过用户写的 2-3 句英文隐式判断，不要直接问"你几级"

收集完 1-3 后调用 save_partial_profile，前端接管展示带宽和写作模式的选择卡片。
    """,
)
```

全部完成后触发 `POST /api/planner/run`，首页显示"今日内容准备中..."。

### LangGraph Tutor Graph 节点

```
[START] → [route_start]
  ├── 有到期词 → [spaced_review] → [reading]
  └── 无到期词 → [reading]

[reading] → [writing_task] → [evaluate_writing] → [save_results] → [END]
```

Tutor 工具：
- `explain_word(word, context)` — 上下文释义
- `analyze_sentence(sentence)` — 长句结构拆解
- `run_feedback(user_text, task, profile)` — 单点突破批改，返回 WritingFeedback Pydantic 模型（仅 1-2 个核心问题 + 重写示范 + 鼓励语）

### API 设计

- `POST /api/onboarding/message` — Onboarding Agent SSE 流式回复
- `GET /api/onboarding/status` — 检查 UserProfile 是否已保存
- `GET /api/lesson/today` — 获取今日 Article + WritingTask
- `POST /api/lesson/action` — SSE，承载 LangGraph Tutor 实时交互（explain_word / analyze_sentence / submit_writing 等 action）
- `GET /api/vocab` — 获取生词本
- `POST /api/planner/run` — 手动触发今日慢循环
- `GET /api/planner/status` — 查询今日课程是否就绪
- `GET /api/profile` — 获取用户配置
- `PATCH /api/profile` — 自然语言更新兴趣

### 前端页面结构

- `/` — 首页（今日状态：复习关卡 or 精读入口）
- `/reading` — 精读页（文章 + 点词弹窗 + 长句分析）
- `/writing` — 写作页（任务卡 + 编辑器 + 提交）
- `/feedback` — 批改页（评分 + 错误高亮 + Rewrite 建议）
- `/vocab` — 生词本页
- `/setup` — 初始化配置对话

## Testing Decisions

**好测试的标准**：只测外部行为，不测实现细节。测试应描述"系统在什么输入下产生什么输出"，而不是"内部调用了哪个函数"。

**测试策略：pytest（纯逻辑）+ LangSmith Eval（LLM 输出质量）**

### pytest 测试（确定性逻辑，无 LLM）

1. **py-fsrs 调度算法**：给定答对/答错序列，验证 `next_review`（由 `fsrs_state["due"]` 同步）和 `fsrs_state` 的更新符合 FSRS 算法预期
2. **每日复习查询**：`VocabItem.next_review <= today` 查询返回正确的词汇集合，过期词和未到期词分别处理正确
3. **Scrapling 爬虫工具**：给定测试 URL，返回纯文本正文，不含广告/导航元素（使用 mock response）
4. **LangGraph 节点路由**：`route_start` 节点在有/无到期词汇时路由到正确的下一节点（mock SQLite 数据）

### LangSmith Eval（LLM 输出质量）

5. **高亮段落标注质量**：Dataset — 给定文章 + 用户目标，评估 `highlight_indices` 选出的段落与目标的相关性；验证 `article_logic` 为有效枚举值
6. **WritingFeedback 批改质量**：Dataset — 给定错误写作样本，评估反馈是否只抓 1-2 个核心问题、是否包含重写示范；同时验证 Pydantic 模型解析成功率
7. **generate_writing_task 任务质量**：评估生成任务是否匹配文章的 `article_logic` 类型

## Out of Scope

- **语音功能**：口语识别、发音训练、实时对话 — 复杂度高、稳定性差，不在当前范围
- **多用户支持**：认证、多账号、云同步 — 纯个人本地工具
- **移动端 App**：不开发 iOS/Android，仅 Web
- **Duolingo 式游戏化**：红心系统、连续打卡火焰、技能树 — 仅保留最小化的复习关卡门控
- **云端部署**：不需要 Vercel/云服务器，纯 localhost
- **多语言支持**：当前只支持中文母语者学习英文
- **实时推荐系统**：基于行为数据的动态推荐算法，超出个人工具复杂度

## Further Notes

- **慢循环触发方式**：MVP 阶段用 `POST /api/planner/run` 手动触发，后续可用 `cron` 定时任务
- **LLM 成本控制**：`highlight_key_paragraphs` 和写作批改是最昂贵的两个调用，可以缓存当日 Article，避免重复生成
- **Scrapling 降级策略**：遇到反爬严重的网站，降级到 Tavily 返回的文章摘要（snippet）直接作为语料
- **py-fsrs 算法参考**：使用 `py-fsrs` 包（FSRS v5），`fsrs_state` 存储完整 Card 序列化状态，`next_review` 字段与 `fsrs_state["due"]` 保持同步，用于 SQLite 快速查询
- **DeepAgents 版本**：使用 `deepagents` PyPI 包，`create_deep_agent()` 返回 compiled LangGraph graph，与 `SqliteSaver` checkpointer 兼容
