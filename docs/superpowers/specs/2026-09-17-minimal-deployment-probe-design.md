# Dayfold P1 最小部署探针设计

状态：默认域名与 Preview 子域名链路已通过，三网多节点访问有条件通过
日期：2026-09-17  
范围：P1 公网连通性验证，不属于 P2 产品实现

## 目标

用最小代码验证以下链路。原设计后端候选为 PythonAnywhere，实际实施因现有账户的唯一 Web app 名额被在运维的 WSGI 站点占用，改用 Render Free 完成同等范围的 FastAPI 公网探针：

```text
GitHub → Vercel 静态 Preview → Render FastAPI /health
```

探针只证明静态页面、HTTPS、CORS 和 API 健康检查可以贯通。它不连接真实日记、数据库、Auth、Dify、模型 Provider 或 Memory Worker。

## 方案比较

### 方案 A：零构建静态页 + FastAPI

- `apps/web` 使用原生 HTML、CSS 和 JavaScript，不引入 Node 依赖。
- 页面允许输入 Render API 地址，点击按钮请求 `/health`。
- `apps/api` 只实现 FastAPI `/health` 和最小 CORS 配置。
- 优点：成本最低、依赖最少、与 P2 产品代码边界清晰。
- 缺点：P2 初始化 React/Vite 时会替换静态 Preview。

### 方案 B：React/Vite + FastAPI 骨架

- 立即初始化计划中的前端技术栈。
- 优点：后续可直接扩展。
- 缺点：会提前进入 P2，带入构建、依赖和设计系统工作，超出 P1 连通性验证范围。

### 方案 C：FastAPI 同时提供页面和 API

- 只部署单个 FastAPI 服务，同时返回 HTML 和 `/health`。
- 优点：部署最少。
- 缺点：无法验证 Vercel → Render 跨域链路，也偏离已确定的前后端分离方向。

## 采用方案

采用方案 A。

Vercel 负责无数据静态 Preview；Render Free 负责 FastAPI `/health`。该部署只作为 P1 Preview 证据，不能冻结为生产承载方案。Render Free 空闲后会休眠，首次唤醒可能超过 Web 当前 10 秒超时，该限制需要与公网验证结果一起保留。

PythonAnywhere 方案未因代码或 FastAPI 兼容性失败而停止。当前免费账户的唯一 Web app 名额已被仍在维护的 Flask WSGI 项目占用；继续使用需要覆盖旧站点或升级双站点套餐。为保护旧项目并控制 P1 成本，本次不在 PythonAnywhere 上部署 Dayfold。

## 文件结构

```text
apps/
├── web/
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   └── vercel.json
└── api/
    ├── main.py
    ├── requirements.txt
    ├── tests/
    │   └── test_health.py
    └── README.md
```

## Web 探针

页面只包含：

- Dayfold Preview 标题与“无真实数据”说明。
- API 地址输入框。
- “检查 API”按钮。
- `idle`、`loading`、`success`、`error` 四种状态。
- 成功时显示 `/health` 返回的公开字段。

API 地址由用户输入，可通过 `?api=https://example.onrender.com` 预填，并保存到浏览器 `localStorage`。地址不是密钥，不写入仓库。

页面不使用 CDN、远程字体、分析脚本或第三方 SDK。

## API 探针

FastAPI 暴露：

```http
GET /health
```

成功响应：

```json
{
  "status": "ok",
  "service": "dayfold-api",
  "environment": "preview",
  "version": "p1-probe"
}
```

响应不包含时间戳、主机名、Git SHA、环境变量、Workflow ID、数据库地址或模型信息，以保持确定性并避免泄露部署细节。

## CORS

- 环境变量：`DAYFOLD_ALLOWED_ORIGINS`
- 格式：逗号分隔的完整 Origin。
- 默认只允许 `http://localhost:8000` 和 `http://127.0.0.1:8000`。
- Preview 部署时显式加入 Vercel HTTPS 域名。
- 不允许 `*`，也不启用跨域凭据。

未知 Origin 必须得不到 `Access-Control-Allow-Origin`。

## 错误处理

- Web 输入为空或不是 `http/https` URL 时，不发送请求。
- 请求超时设为 10 秒。
- HTTP 非 2xx、JSON 无法解析或字段不符合契约时显示错误状态。
- 错误信息不回显响应正文，避免意外展示服务内部信息。
- API 保持 FastAPI 默认异常处理，不增加日志上报或外部监控。

## Render 部署边界

部署使用 Render Python Web Service 和 Uvicorn：

```text
Root Directory: apps/api
Build Command: pip install -r requirements.txt
Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
```

部署说明必须明确：

- Free 实例会在空闲后休眠，不能据此承诺稳定响应时间。
- 本地文件系统不承担持久化职责。
- Render 凭据、Deploy Hook 和其他 Secret 不进入仓库。
- 平台设置变化时，以 Render 当前官方文档为准。

## 测试

自动验证：

- `/health` 返回 200 和固定 JSON。
- 配置的 Origin 获得正确 CORS 响应。
- 未配置 Origin 不获得允许头。
- Web JavaScript 不包含密钥模式或固定部署用户名。
- HTML、CSS、JavaScript 和 `vercel.json` 均可做静态检查。

手动验证：

- Vercel Preview 能通过 HTTPS 打开。
- 页面能请求 Render `/health` 并显示成功。
- 移动、联通、电信至少各完成一次访问记录。
- 浏览器控制台无跨域和混合内容错误。

## 验收标准

1. 本地测试全部通过。
2. Web 与 API 均不包含真实用户数据或凭据。
3. Vercel 页面可访问。
4. Render `/health` 返回固定 200 JSON。
5. Vercel → Render 跨域请求成功。
6. 部署结果明确标记为 Preview，不作为生产可用性承诺。

## 非目标

- 不实现 React/Vite 产品界面。
- 不实现登录、数据库、日记、Memory、SSE 或 Worker。
- 不调用 Dify、硅基流动或其他模型。
- 不配置 `dayfold.com.cn` 根域名或 `www` 正式入口；只允许隔离的 Preview 子域名。
- 不宣称 Render 是最终生产平台。

## 参考

- [Render：Deploy a FastAPI App](https://render.com/docs/deploy-fastapi)
- [Render：Deploy for Free](https://render.com/docs/free)
