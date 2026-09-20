# Dayfold P1 Minimal Deployment Probe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用最小代码验证 Vercel 静态 Preview 到 PythonAnywhere FastAPI `/health` 的 HTTPS 与 CORS 连通性。

**Architecture:** `apps/web` 是无构建依赖的 HTML/CSS/JavaScript 页面，只负责收集 API Origin、请求 `/health` 并展示四种状态。`apps/api` 是只暴露固定健康响应的 FastAPI 应用，CORS Origin 从环境变量白名单读取，默认仅允许本地静态服务器。

**Tech Stack:** HTML、CSS、Vanilla JavaScript、Python 3.10、FastAPI、Uvicorn、Pytest、HTTPX

---

## File Map

- `apps/api/main.py`：FastAPI 应用、固定健康响应、CORS 白名单解析。
- `apps/api/requirements.txt`：运行与测试所需的最小 Python 依赖。
- `apps/api/tests/test_health.py`：健康响应与 CORS 行为测试。
- `apps/api/README.md`：本地运行和 PythonAnywhere Preview 部署说明。
- `apps/web/index.html`：无真实数据的探针页面结构。
- `apps/web/styles.css`：遵循 Dayfold 纸张视觉合同的最小样式。
- `apps/web/app.js`：URL 校验、超时、响应契约和四态渲染。
- `apps/web/vercel.json`：静态 Preview 配置与安全响应头。

### Task 1: API contract tests

**Files:**
- Create: `apps/api/tests/test_health.py`
- Create: `apps/api/requirements.txt`

- [ ] 写入测试，要求 `/health` 返回 `200` 与以下精确 JSON：

```python
{
    "status": "ok",
    "service": "dayfold-api",
    "environment": "preview",
    "version": "p1-probe",
}
```

- [ ] 写入允许 Origin 和未知 Origin 的 CORS 测试。
- [ ] 安装 `requirements.txt` 后运行：

```bash
python3 -m pytest apps/api/tests/test_health.py -v
```

预期：因 `apps.api.main` 尚不存在而失败，证明测试处于 RED。

### Task 2: Minimal FastAPI app

**Files:**
- Create: `apps/api/main.py`

- [ ] 实现逗号分隔的 `DAYFOLD_ALLOWED_ORIGINS` 解析；未设置时使用：

```python
(
    "http://localhost:8000",
    "http://127.0.0.1:8000",
)
```

- [ ] 拒绝 `*`，配置 `CORSMiddleware` 且保持 `allow_credentials=False`。
- [ ] 实现唯一业务路由 `GET /health`。
- [ ] 再次运行 API 测试，预期全部通过。

### Task 3: Static web contract

**Files:**
- Create: `apps/web/index.html`
- Create: `apps/web/styles.css`
- Create: `apps/web/app.js`
- Create: `apps/web/vercel.json`
- Extend: `apps/api/tests/test_health.py`

- [ ] 先增加静态检查，验证四个文件存在、`vercel.json` 是合法 JSON、页面包含 Dayfold Preview 与无真实数据说明。
- [ ] 检查 JavaScript 不包含 API Key 模式、固定 PythonAnywhere 用户名或硬编码生产 API。
- [ ] 运行测试并确认因静态文件缺失而失败。
- [ ] 实现页面的 `idle`、`loading`、`success`、`error` 状态。
- [ ] API 地址只接受 `http:` 或 `https:`，移除尾部斜杠后请求 `/health`。
- [ ] 使用 `AbortController` 设置 10 秒超时，不展示响应正文或内部错误。
- [ ] 校验成功 JSON 的四个字段与固定契约完全一致。
- [ ] 支持 `?api=` 预填和 `localStorage` 保存，不内置部署域名。
- [ ] 再次运行测试，预期全部通过。

### Task 4: Documentation and verification

**Files:**
- Create: `apps/api/README.md`
- Delete: `apps/api/.gitkeep`
- Delete: `apps/web/.gitkeep`

- [ ] 记录本地安装、启动、环境变量和测试命令。
- [ ] 明确 PythonAnywhere ASGI 为 beta Preview，不是生产平台决定。
- [ ] 明确不提交 API Key、Token 或真实用户数据。
- [ ] 运行：

```bash
python3 -m compileall -q apps/api
python3 -m pytest apps/api/tests -v
python3 -m unittest discover -s evals/memory/tests -v
git diff --check
```

- [ ] 启动 Uvicorn 与本地静态服务器，使用真实 HTTP 请求验证 `/health`、允许 Origin、未知 Origin和 OPTIONS 预检。
- [ ] 检查 `git status` 与 `git diff --stat`，确认没有修改 P1 Memory 评测资产、产品文档或未跟踪 ZIP。

## Out of Scope

- React、Vite、TypeScript
- 数据库、Auth、Memory、Retrieval、Chat、SSE、Worker
- Dify、模型 Provider、真实用户数据
- Vercel 与 PythonAnywhere 账户操作
- 正式域名、生产架构或 P2 初始化
