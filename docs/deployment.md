# DynamicLingo 部署记录

**部署日期：** 2026-03-22

---

## 部署概览

| 服务 | 平台 | URL |
|------|------|-----|
| 后端 (FastAPI) | Render (free tier) | https://happy-ielts.onrender.com |
| 前端 (Next.js) | Vercel | https://frontend-chi-opal-61.vercel.app |

---

## 验证结果

### 后端 /health

```bash
curl https://happy-ielts.onrender.com/health
# → {"status":"ok"}  HTTP 200
```

- 冷启动时间：~148 秒（Render 休眠后首次唤醒）
- 正常响应时间：< 1 秒

### 前端

| 页面 | 状态 |
|------|------|
| `/onboarding` | ✅ SSE 流式消息正常 |
| `/lesson` | ✅ 文章加载、写作 feedback、生词记录正常 |

---

## 保活方案（Google Apps Script）

**背景：** Render 免费层 15 分钟无请求自动休眠，需在使用窗口内每 10 分钟 ping 一次。

**保活窗口：** SGT 18:00–23:59（UTC 10:00–15:59）

**脚本代码：**

```javascript
var BACKEND_URL = "https://happy-ielts.onrender.com/health";

function keepAlive() {
  var now = new Date();
  var utcMs = now.getTime() + now.getTimezoneOffset() * 60000;
  var sgt = new Date(utcMs + 8 * 3600000);
  var hour = sgt.getHours();

  if (hour >= 18) {
    try {
      var resp = UrlFetchApp.fetch(BACKEND_URL, { muteHttpExceptions: true });
      console.log("✓ keepAlive OK | SGT " + hour + ":00 | status=" + resp.getResponseCode());
    } catch (e) {
      console.error("✗ keepAlive FAIL: " + e.message);
    }
  } else {
    console.log("- skip (SGT " + hour + ":00, outside window)");
  }
}
```

**触发器配置：**

1. 访问 https://script.google.com → 项目名：`DynamicLingo KeepAlive`
2. 左侧 ⏰ 触发器 → 添加触发器
3. 函数：`keepAlive` | 时间驱动 | 分钟计时器 | 每 10 分钟

---

## 注意事项

| 项目 | 说明 |
|------|------|
| 冷启动延迟 | SGT 18:00 第一次请求等 30–148 秒，之后正常 |
| SQLite 持久化 | 确认 Render 已挂载 Persistent Disk，否则重启后数据丢失 |
| Render 用量 | 保活 6h/天 × 30 = 180h/月，750h 限额内安全 |
| 环境变量 | `DASHSCOPE_API_KEY`、`TAVILY_API_KEY` 在 Render 后台配置 |

---

## 快速排障

```bash
# 检查后端是否存活
curl https://happy-ielts.onrender.com/health

# 本地开发
task dev:backend   # FastAPI :8000
task dev:frontend  # Next.js :3000
```

Render 日志：Dashboard → Logs，正常请求：
```
GET /health 200
POST /api/onboarding/message 200
GET /api/lesson/today 200
```
