# Dayfold API Preview

这是 Dayfold Portfolio MVP 的 FastAPI 服务。现有接口包含健康检查、Staging Auth
探针、Demo Mode 配置和 Today Entry CRUD。

## 本地运行

在仓库根目录安装依赖：

```bash
python3 -m pip install --break-system-packages -r apps/api/requirements.txt
```

启动 API：

```bash
python3 -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8001
```

另开一个终端启动静态页面：

```bash
python3 -m http.server 8000 --directory apps/web
```

打开 `http://localhost:8000`，在页面中输入 `http://127.0.0.1:8001`。

## CORS 白名单

默认只允许本地静态服务器：

```text
http://localhost:8000
http://127.0.0.1:8000
```

Preview 部署必须通过环境变量显式传入完整 Origin，多个值用逗号分隔：

```bash
export DAYFOLD_ALLOWED_ORIGINS="https://your-preview.example"
```

配置不接受 `*`，也不启用跨域凭据。

## Portfolio Demo Mode

Demo Mode 默认关闭。只在使用虚构数据的 Portfolio 环境中启用：

```bash
export DAYFOLD_DEMO_MODE=true
export DAYFOLD_DATABASE_PATH="$PWD/local/dayfold-demo.sqlite3"
```

Demo Mode 使用固定合成用户，客户端不能提交 `user_id`。本地默认使用 SQLite。

### 在线持久化

CloudBase Run 容器的本地文件不作为持久化事实来源。Portfolio 在线环境使用远程
Turso 数据库，同时保持现有 SQLite Schema 和 Repository SQL：

```bash
export DAYFOLD_DATA_BACKEND=turso
export TURSO_DATABASE_URL="<server-side database URL>"
export TURSO_AUTH_TOKEN="<server-side secret>"
```

`TURSO_DATABASE_URL` 和 `TURSO_AUTH_TOKEN` 必须只配置在 API 部署平台。缺少任意一项
时服务会明确失败，不会静默回退到容器临时 SQLite。未设置
`DAYFOLD_DATA_BACKEND` 时，本地开发继续使用：

```bash
export DAYFOLD_DATA_BACKEND=sqlite
export DAYFOLD_DATABASE_PATH="$PWD/local/dayfold-demo.sqlite3"
```

部署前使用两个独立数据库连接执行写入、读取和清理验证：

```bash
python3 -m apps.api.scripts.verify_persistence
```

只有脚本返回 `status=passed` 才能继续线上 API 验收。

Today Entry 接口：

```text
POST   /v1/entries
GET    /v1/entries
GET    /v1/entries/{entry_id}
PATCH  /v1/entries/{entry_id}  If-Match: <version>
DELETE /v1/entries/{entry_id}
```

所有时间必须包含时区并在服务端归一化为 UTC。删除为软删除，已删除记录不会出现在读取
结果中。

## LLM Chat

Chat 使用服务端方舟 API Key，前端不会接触凭证：

```bash
export DAYFOLD_LLM_API_KEY="<server-side secret>"
export DAYFOLD_LLM_ENDPOINT="https://ark.cn-beijing.volces.com/api/plan/v1/messages"
export DAYFOLD_LLM_MODEL="doubao-seed-2-1-turbo"
```

也兼容现有本地验证变量 `DAYFOLD_ARK_API_KEY`、`DAYFOLD_ARK_BASE_URL` 和
`DAYFOLD_ARK_MODEL`。不要把变量值写入仓库或命令历史。

最小 Chat 接口：

```text
POST /v1/conversations
GET  /v1/conversations/{conversation_id}/messages
POST /v1/conversations/{conversation_id}/messages/stream
```

流接口返回 `text/event-stream`，事件顺序为 `message.start`、一个或多个
`message.delta`、最后 `message.done`。Provider 失败时返回 `message.error`；
用户消息保留，系统不会写入虚假的助手回复。

## Memory Extraction

对当前 Demo User 的日记或用户消息执行提取：

```text
POST /v1/memory-extractions
{"source_type":"entry|message","source_id":"<resource id>"}
```

服务使用 `apps/api/prompts/memory_extraction_v0_4.md`，只接受经过严格校验的
`event`、`interest`、`goal` upsert。Memory 与来源关系在同一事务保存；未知类型、
缺失字段、越界置信度或非 JSON 输出不会部分落库。助手消息不能作为 Memory 来源。

## Embedding 与 Retrieval

Embedding 使用标准方舟 API，不使用 Agent Plan Chat Key：

```bash
export DAYFOLD_EMBEDDING_API_KEY="<server-side standard Ark secret>"
export DAYFOLD_EMBEDDING_ENDPOINT="https://ark.cn-beijing.volces.com/api/v3/embeddings/multimodal"
export DAYFOLD_EMBEDDING_MODEL="doubao-embedding-vision-251215"
export DAYFOLD_EMBEDDING_DIMENSIONS="1024"
```

接口：

```text
POST /v1/memory-embeddings/sync
POST /v1/memory-retrievals
{"query":"职业方向让我有些迷茫","limit":5}
```

同步接口只处理当前 Demo User 尚未索引的 Active Memory。检索只比较同一租户、
同一模型、同一维度且状态为 Active 的向量。当前 SQLite 实现以 JSON 保存向量并执行
精确 cosine search，适合小规模 Portfolio Demo；上线持久化数据库阶段再替换为
pgvector 索引。

## AI Recall

Chat 在调用 LLM 前自动执行：

```text
同步未索引 Active Memory
→ 查询消息 Embedding
→ 租户内 cosine retrieval
→ 相关性过滤
→ Memory Context 注入
→ SSE 回复
```

默认召回阈值为 `0.30`，可通过 `DAYFOLD_RECALL_MIN_SCORE` 覆盖。该默认值来自标准方舟
Embedding 的真实中文语义验证；示例职业方向问题与对应 Goal 的 cosine score 约为
`0.335`。`message.start` 会返回被采用的 Memory ID、类型与分数，便于验证来源，但
不会暴露其他用户数据。

## 最近的你

```text
GET /v1/growth/current
```

只有当前用户至少存在 `2` 条 Active Memory，且来自至少 `2` 个不同来源时，服务端
才调用 LLM 生成一到两句“最近的你”。总结与 Memory、Entry/Message 来源关系在同一
事务保存。证据不足时固定返回：

```json
{
  "status": "collecting",
  "content": "正在积累你的记录。",
  "evidence": []
}
```

Growth 不使用其他用户数据，也不会在证据不足时推测趋势。

## Memory Control

```text
GET    /v1/memories
GET    /v1/memories/{memory_id}
PATCH  /v1/memories/{memory_id}
DELETE /v1/memories/{memory_id}
```

详情接口返回 Memory 与来源。PATCH 当前只接受 `{"status":"disabled"}`；Disable
会立即删除对应 Embedding，使其退出后续召回。Delete 会确定性清理来源、Embedding
和引用该 Memory 的 Growth 证据，不调用 LLM。所有对象操作绑定当前 Demo User，
不存在与跨用户访问统一返回 `404 RESOURCE_NOT_FOUND`。

## 自动测试

```bash
python3 -m pytest apps/api/tests -v
```

## PythonAnywhere Preview

PythonAnywhere 的 ASGI 支持仍是 beta，本配置只用于 P1 公网连通性验证，不代表 Dayfold 的生产部署平台已经冻结。

示例进程命令：

```text
$HOME/.virtualenvs/dayfold-probe/bin/uvicorn --app-dir $HOME/dayfold/apps/api --uds ${DOMAIN_SOCKET} main:app
```

部署时需要：

1. 在平台环境中设置 `DAYFOLD_ALLOWED_ORIGINS` 为实际 Vercel HTTPS Origin。
2. 使用平台当前文档提供的 ASGI 建站命令绑定上述进程。
3. 分别验证直接访问 `/health` 与 Vercel 页面跨域请求。

API Key、平台 Token、真实日记、私人对话和任何用户数据都不得写入仓库、页面或测试结果。

## Staging Auth 会话验证

`apps.api.scripts.staging_auth_sessions` 用于验证账户注销补偿控制下的两设备 AccessToken 和 RefreshToken 行为。脚本不创建、冻结或删除账号，只读取环境变量中的两组虚构会话凭据，并输出不含凭据的 JSON 结果。

运行前，Staging API 必须提供一个只读受保护探针：

```text
GET /v1/auth/probe
active 用户 -> 200
deletion_pending、disabled、缺失映射或已删除用户 -> 401
状态存储未配置或不可用 -> 503
```

当前 CloudBase 个人版共享 PostgreSQL 通过 HTTP API 提供状态查询。部署需要配置：

```text
DAYFOLD_USER_STATUS_BACKEND=cloudbase_http
DAYFOLD_CLOUDBASE_ENV_ID=<environment id>
```

该后端把已通过 CloudBase 身份验证的当前用户 AccessToken 转发给 PostgreSQL HTTP
API，并由 `users_select_self` RLS Policy 限制为只能读取自身未删除的内部状态。
不需要 `DATABASE_URL`、数据库密码或管理员 API Key。只有状态为 `active` 的内部用户
映射可以通过；状态接口异常时门禁返回 `503 USER_STATUS_UNAVAILABLE`。

如未来切换到原生 PostgreSQL 直连，则显式配置：

```text
DAYFOLD_USER_STATUS_BACKEND=postgres
DATABASE_URL=<server-side secret>
```

不得把数据库连接串、Token 或 API Key 写入 Git、命令参数或验证报告。

需要设置：

```text
DAYFOLD_CLOUDBASE_ENV_ID
DAYFOLD_STAGING_PROTECTED_URL
DAYFOLD_DEVICE_A_ACCESS_TOKEN
DAYFOLD_DEVICE_A_REFRESH_TOKEN
DAYFOLD_DEVICE_B_ACCESS_TOKEN
DAYFOLD_DEVICE_B_REFRESH_TOKEN
```

`DAYFOLD_CLOUDBASE_CLIENT_ID` 可省略，默认使用环境 ID。只有目标环境明确要求时才通过 Secret 管理设置 `DAYFOLD_CLOUDBASE_CLIENT_SECRET`。

当前 Staging-equivalent 探针：

```text
DAYFOLD_STAGING_PROTECTED_URL=https://dayfold-api-staging-317758-12-1442808051.sh.run.tcloudbase.com/v1/auth/probe
```

该服务位于 CloudBase 免费 Preview 环境，仅用于虚构账号验证，不构成独立 Staging 环境或生产批准。

不要把 Token 写在命令参数、脚本、`.env`、终端历史或报告中。应通过 CI Secret、部署平台 Secret，或终端的静默输入功能注入当前进程环境。

先在两个独立浏览器配置或设备上登录同一虚构账号，然后运行基线：

```bash
python3 -m apps.api.scripts.staging_auth_sessions baseline
```

基线要求两台设备的旧 AccessToken 均可访问 CloudBase 和 Dayfold，且
`sub` 一致。脚本允许两种 RefreshToken 契约：

```text
multi_device        两台设备均可换发
latest_session_only 仅最后登录设备可换发，较早设备返回 4xx
```

至少一台设备必须成功换发，并且新 AccessToken 必须同时通过 CloudBase
身份接口和 Dayfold 探针；两枚 RefreshToken 都被拒绝时基线失败。结果中的
`refresh_contract` 会记录实际契约。

确认注销后，在控制状态达到 `identity_disabled` 时运行：

```bash
python3 -m apps.api.scripts.staging_auth_sessions blocked
```

删除身份并确认 UID 不存在后运行：

```bash
python3 -m apps.api.scripts.staging_auth_sessions deleted
```

如果 RefreshToken 已被拒绝，脚本记录 `refresh_denied=true`。如果 CloudBase 仍签发新 AccessToken，只有该 Token 被 Dayfold 受保护探针拒绝时阶段才通过。退出码 `0` 表示通过，`1` 表示验证失败；可用 `--output <path>` 写入不含凭据的 JSON 结果。
