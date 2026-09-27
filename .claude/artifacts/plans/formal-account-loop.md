# Dayfold 正式账号闭环实施方案

> Status: APPROVED
> Source: `docs/p2/dayfold-p2-technical-specification.md`、`docs/superpowers/specs/2026-09-23-cloudbase-http-user-status-design.md`、用户当前请求
> Mode: --deliberate
> Iterations: 2 / 3
> Last updated: 2026-09-25

## Requirements summary

将当前固定 Demo User 的 Portfolio Demo 攸关路径改造成受邀正式账号可登录、可恢复会话、可退出、且所有业务数据按真实内部 `user_id` 隔离的私人应用。首个切片不开放公开注册、不迁移 Demo 数据、不实现账号注销；这些能力保持为后续 Production Gate，正式账号仅限受邀小范围使用。

当前已存在 CloudBase AccessToken 校验、内部用户状态门禁和 `user_id` 绑定 Repository。本方案补齐浏览器认证、内部 UUID 映射、业务路由统一鉴权、生产配置和双账号隔离验收。

## Scope

### In scope

- CloudBase Auth v2 邮箱密码登录。
- CloudBase SDK 自动恢复和刷新会话。
- 退出登录并清空当前浏览器会话。
- 受邀账号在 CloudBase `public.users` 中预置内部 UUID 映射。
- FastAPI 统一 `AuthContext` 依赖。
- Today、Chat、Memory、Embedding、Recall、Growth 全部使用认证用户的内部 UUID。
- 所有普通 API 请求和 SSE 请求发送 Bearer Token。
- 未登录、Token 失效、非 `active`、缺失映射和状态服务异常时 fail closed。
- Production 关闭 Demo Mode，清理固定 Demo User 的合成数据。
- 两个虚构账号完成跨租户隔离 E2E。

### Out of scope

- 公开注册和邮箱验证码注册。
- 找回密码、自助修改密码和账号资料编辑。
- 账号注销、身份冻结和业务数据清理控制面。
- Demo 数据迁移到正式账号。
- Chat 从 Agent Plan 迁移到标准方舟；它是独立稳定性任务。
- React 重写、导航重构或视觉风格改版。

## Acceptance criteria

- **AC-1**：未携带 Bearer Token 访问任一业务路由均返回 `401 INVALID_TOKEN`；`/health` 保持公开。
- **AC-2**：受邀账号可通过邮箱密码登录，刷新页面后 SDK 恢复会话，退出后业务请求立即返回 `401`。
- **AC-3**：API 将 CloudBase `sub` 映射为 CloudBase `public.users.id` 内部 UUID；业务模块和 Repository 不接收前端提交的 `user_id`。
- **AC-4**：仅 `status=active` 且 `deleted_at IS NULL` 的唯一映射可进入业务路由；缺失、重复、禁用和状态服务故障均拒绝。
- **AC-5**：两个虚构账号分别创建 Entry、Conversation、Memory、Embedding 和 Growth 后，只能读取和修改自己的数据；跨租户对象访问统一返回 `404`。
- **AC-6**：普通 JSON 请求和 Chat SSE 请求都发送同一当前 AccessToken；Token 刷新后无需刷新页面即可继续请求。
- **AC-7**：Production 设置 `DAYFOLD_DEMO_MODE=false`，Web 不再显示 API Origin 设置和 Demo User 状态。
- **AC-8**：AccessToken、RefreshToken、密码、CloudBase API Key 不进入 Git、日志、数据库或错误响应；浏览器只配置环境 ID 与地域。
- **AC-9**：Production 切换前完成备份和 Demo 数据清理；失败时可回滚至当前 Demo 部署，不发生正式用户数据混写。

## RALPLAN-DR

### Principles

- 身份先验证、状态再授权、业务层只接收内部 `user_id`。
- 复用现有 CloudBase Auth Adapter 和 RLS，不引入第二套身份供应商。
- 首个切片只服务受邀账号，不把公开注册和注销混入。
- Token 只由 CloudBase SDK 管理，应用代码不持久化 Token。
- 所有生产切换必须可回滚，Demo 数据不得归属到正式账号。

### Decision drivers

1. **安全边界**：真实日记和记忆必须按内部 UUID 隔离。
2. **交付速度**：复用已验证的 CloudBase Token、RLS 和状态门禁。
3. **运行复杂度**：当前 Web 为静态站点、API 为 Vercel、业务数据库为 Turso。

### Viable options

#### Option A：CloudBase Web SDK + Bearer Token + FastAPI AuthContext

- Web 使用固定版本 CloudBase JS SDK；SDK 管理 Session 和 Token 刷新。
- 每次请求从 SDK 读取当前 Session，将 AccessToken 放入 `Authorization`。
- FastAPI 验证 Token，查询 CloudBase `users` 映射并返回内部 UUID。
- **Pros**：符合既有技术规范；复用已验证 Adapter/RLS；静态 Web 仍可独立部署。
- **Cons**：Token 存在浏览器 SDK 管理的客户端会话中；必须控制 XSS 和重复初始化。

#### Option B：FastAPI BFF + HttpOnly Session Cookie

- Web 将登录请求发给 FastAPI，API 持有 CloudBase Token 并签发 HttpOnly Cookie。
- **Pros**：浏览器 JavaScript 不接触 AccessToken；服务端可统一 Session 策略。
- **Cons**：需要新增 Session Store、CSRF 防护、跨域 Cookie、刷新 Token 持久化和密钥轮换；Web/API 不同域名使部署复杂度显著增加。

### Favored option

选择 **Option A**。当前 CloudBase Auth Adapter、状态门禁和静态 Web 架构都围绕 Bearer Token 建立，Option A 能最小化新增状态与跨域 Cookie 风险。通过 SDK 单例、禁止动态 HTML 注入、固定依赖版本和严格 CSP 控制客户端风险。

## Implementation steps

### Phase 0：工作区与基线

1. 从最新 `main` 创建 `codex/formal-account-loop` worktree；保留主目录未跟踪的 ZIP 和 `test-results/`，不得带入分支。
2. 运行 `python3 -m pytest apps/api/tests -q`、`python3 -m compileall -q apps/api app.py`，记录基线。
3. 新增修复/实施跟踪文档 `.claude/artifacts/fixes/formal-account-access.md`，记录当前 Demo-only 根因和验收证据。

### Phase 1：内部用户映射契约

4. 在 `apps/api/auth/user_status.py` 新增只读值对象 `InternalUser(id, auth_subject, status)`，把状态存储契约从 `get_status()` 收敛为 `get_user()`。
5. 修改 `CloudBaseHttpUserStatusStore` 的查询列为 `id,auth_subject,status`，验证返回 UUID、唯一 subject 和合法状态；异常数据返回 `UserStatusStoreUnavailable`。
6. 保留 `PostgresUserStatusStore` 兼容实现，同样返回 `InternalUser`。
7. 修改 `infra/cloudbase/migrations/20260923_users_select_self.sql`，给 `authenticated` 增加 `id` 列 SELECT 权限；不增加 INSERT、UPDATE、DELETE 权限。
8. 更新 `apps/api/tests/test_user_status.py`：覆盖合法 UUID、非法 UUID、subject 不匹配、重复行、非 active 状态和供应商异常。

### Phase 2：统一 AuthContext

9. 新建 `apps/api/auth/context.py`，定义 `AuthContext(user_id, auth_subject, email)`，不保存 Token。
10. 在 `apps/api/main.py` 增加 `get_auth_context()` 依赖：
    - 严格解析 Bearer；
    - 调用 `CloudBaseAuthAdapter.verify_access_token()`；
    - 调用 `UserStatusStore.get_user()`；
    - 仅 `active` 返回 `AuthContext`；
    - 统一映射 `401 INVALID_TOKEN` 与 `503 AUTH_PROVIDER_UNAVAILABLE/USER_STATUS_UNAVAILABLE`。
11. 将 `/v1/auth/probe` 改为复用 `get_auth_context()`，避免认证逻辑复制。
12. 新增 `GET /v1/auth/session`，只返回 `{"status":"authenticated"}`，不回传内部 UUID、email 或 subject。
13. 在 `apps/api/tests/test_auth_probe.py` 新增 AuthContext 与 session 测试，证明 Token 原文不会进入对象、日志和响应。

### Phase 3：业务路由切换

14. 在 `apps/api/main.py` 将所有业务路由的 `DemoSettings` 依赖替换为 `AuthContext`：
    - Entries；
    - Conversations / Messages / SSE；
    - Memory Extraction / Memory Control；
    - Embedding Sync / Retrieval；
    - Growth。
15. 每个路由只使用 `auth.user_id` 调用现有 Repository；不得引入前端 `user_id` 字段。
16. 保留 `/v1/demo` 仅用于显式 `DAYFOLD_DEMO_MODE=true` 的本地/演示部署；Production 关闭时返回 `404`。
17. 更新现有 API 测试 fixture：默认注入 `AuthContext`；新增未认证 `401` 与跨租户 `404` 回归测试。

### Phase 4：Web Auth 单例与 UI

18. 在 `apps/web/package.json` 固定 CloudBase JS SDK 版本并增加最小 Vite 构建；不迁移到 React。
19. 新建 `apps/web/auth-client.js`：
    - 只初始化一个 CloudBase app/auth 实例；
    - `getSession()` 获取当前 Session；
    - `signInWithPassword({email,password})` 登录；
    - `signOut()` 退出；
    - `onAuthStateChange()` 同步 `INITIAL_SESSION`、`SIGNED_IN`、`SIGNED_OUT`、`TOKEN_REFRESHED`；
    - 暴露 `getAccessToken()`，不把 Token 写入应用 localStorage。
20. 新建 `apps/web/public-config.js`，仅包含环境 ID 与地域；不传递任何 Key。
21. 修改 `apps/web/index.html` 增加登录视图、会话恢复状态、退出按钮和认证错误区域；保持当前横线纸与单列布局。
22. 修改 `apps/web/styles.css`，只增加认证视图所需样式，不重构现有设计系统。
23. 修改 `apps/web/app.js`：
    - 启动时先恢复 Session，再决定显示登录页或应用；
    - `api()` 自动添加 Bearer Token；
    - Chat SSE `fetch` 同样添加 Bearer Token；
    - `401` 统一切回登录页并清理当前页面状态；
    - 移除 Production API Origin 设置入口；
    - 不再调用 `/v1/demo` 判断连接。
24. 使用 Node 内建测试或轻量 DOM 测试覆盖 SDK 单例、Token 注入、401 退回登录页和 SSE Authorization。

### Phase 5：生产配置与数据切换

25. 在 CloudBase 控制台：
    - 启用邮箱密码登录；
    - 配置 `www.dayfold.com.cn` 允许来源；
    - 核对当前 SDK 快速开始契约仅要求环境 ID 与地域；
    - 创建至少两个虚构受邀账号。
26. 在 CloudBase `public.users` 为两个虚构账号预置不同内部 UUID，状态为 `active`；执行更新后的 RLS migration 并验证只能读取自身行。
27. 在 Vercel API 设置：
    - `DAYFOLD_DEMO_MODE=false`；
    - `DAYFOLD_CLOUDBASE_ENV_ID`；
    - `DAYFOLD_USER_STATUS_BACKEND=cloudbase_http`；
    - 保留 Turso 与 Ark 服务端 Secret。
28. 在 Web 设置公开环境 ID与地域；不得配置 API Key、RefreshToken 或管理员 Secret。
29. 备份 Turso 后删除固定 Demo User 的全部合成 Entry、Message、Memory、Embedding 和 Growth 数据；记录删除数量，不记录内容。

### Phase 6：上线验收

30. 本地运行 API、Web 单测与构建。
31. 在 Preview 部署用两个虚构账号执行：
    - 登录、刷新恢复、退出；
    - A/B 各自创建 Entry → Memory → Embedding → Recall → Growth；
    - A 访问 B 的每类资源均为 `404`；
    - 旧/伪造/过期 Token 为 `401`；
    - `disabled` 用户为 `401`；
    - CloudBase 状态服务故障为 `503`。
32. Production 先发布 API，再发布 Web；未认证浏览器必须停在登录页。
33. 观察 30 分钟：认证 `401/503`、CloudBase 延迟、Turso 错误和 Chat Provider 错误分开记录。
34. 验收失败时回滚 Web 到 Demo 版本并保持 Production 写入关闭；不得把固定 Demo User 重新开放给真实数据。

## Workspace setup

- 实施前运行 `git status --short` 和 `git branch --show-current`。
- 当前主目录位于 `main`，且有未跟踪 ZIP 与 `test-results/`；实施必须创建独立 worktree。
- 推荐命令：`git worktree add -b codex/formal-account-loop ../dayfold-formal-account-loop main`。
- worktree 中只包含 Git 追踪文件；凭证仍通过 macOS 钥匙串或部署平台 Secret 注入。

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| SDK 重复初始化导致 `Duplicate component auth` | `auth-client.js` 模块级单例；初始化测试与无痕浏览器 E2E |
| Token 泄露到日志或 localStorage | 只使用 SDK Session；应用不持久化 Token；错误归一化；提交前精确 Secret 扫描 |
| CloudBase `sub` 被直接当业务主键 | `UserStatusStore` 强制返回内部 UUID；业务路由只接收 `AuthContext.user_id` |
| 状态查询跨服务增加延迟/故障域 | 3 秒超时、fail closed、独立 `503` 错误码；不缓存过期身份 |
| 两个账号数据混写 | 所有 Repository 继续显式 `user_id`；双账号跨租户 E2E |
| Demo 数据误归属正式账号 | 不迁移；备份后按固定 Demo UUID 清理 |
| SDK Token 刷新后 API 仍使用旧 Token | 每次请求从当前 Session 取 Token；监听 `TOKEN_REFRESHED`；刷新 E2E |
| Web 已登录但内部映射缺失 | 登录后 `/v1/auth/session` 返回通用 `401`；受邀账号上线前预置映射 |
| Auth 上线但 Chat 仍 503 | 独立记录 Provider 错误；账号闭环验收不把 Chat 稳定性误判为 Auth 失败 |

## Verification steps

- `python3 -m pytest apps/api/tests/test_user_status.py -q`
- `python3 -m pytest apps/api/tests/test_auth_probe.py -q`
- 新增业务鉴权矩阵测试：每类路由分别验证 `401 / own 2xx / foreign 404`。
- `python3 -m pytest apps/api/tests -q`
- `python3 -m compileall -q apps/api app.py`
- `npm test --prefix apps/web`
- `npm run build --prefix apps/web`
- `git diff --check`
- Preview 双账号浏览器 E2E。
- Production `/health=200`、未认证业务路由 `401`、登录后 `/v1/auth/session=200`。
- 提交前比较钥匙串中的真实 Secret 与 staged diff，匹配数必须为 0。

## Pre-mortem

1. **Scenario**：用户登录成功但所有业务请求持续 `401`。
   **Trigger**：CloudBase Session 有效，`/auth/v2/user/me=200`，但 `users` 映射为空。
   **Mitigation**：上线前预置受邀映射；`get_user()` 验证 id/subject/status；缺失映射保持通用 `401`。

2. **Scenario**：A 用户看到 B 用户的日记或记忆。
   **Trigger**：某条路由继续使用固定 Demo UUID，或漏传 `AuthContext.user_id`。
   **Mitigation**：逐路由移除 `DemoSettings`；业务鉴权矩阵和双账号 E2E 覆盖所有资源类型。

3. **Scenario**：SDK 初始化两次，线上再次出现 `Duplicate component auth`。
   **Trigger**：页面启动和登录表单各自调用 CloudBase init。
   **Mitigation**：唯一 `auth-client.js` 单例；禁止其他模块直接 import/init SDK；无痕刷新与重复挂载测试。

4. **Scenario**：CloudBase 故障时前端误认为用户退出并丢失编辑内容。
   **Trigger**：API 返回 `503 AUTH_PROVIDER_UNAVAILABLE`，前端按 `401` 处理。
   **Mitigation**：401 与 503 分离；只有 401 清会话，503 显示维护状态并禁止写入。

## Expanded test plan

- **Unit**：Token 解析、AuthContext、InternalUser 校验、SDK 单例、Token 注入、401/503 UI 分流。
- **Integration**：CloudBase Auth MockTransport + User Store + FastAPI 业务路由；Turso Repository 仍按内部 UUID 查询。
- **E2E**：两个虚构账号执行登录、刷新、退出、全业务链路和跨租户攻击矩阵。
- **Observability**：按 `INVALID_TOKEN`、`AUTH_PROVIDER_UNAVAILABLE`、`USER_STATUS_UNAVAILABLE`、AI Provider 错误分组计数；日志不得记录 Token、email 或内容。

## ADR

- **Decision**：使用 CloudBase Web SDK 管理浏览器 Session，以 Bearer Token 调用 FastAPI；API 每次验证 Token 并将 CloudBase subject 映射为 CloudBase `users.id` 内部 UUID后进入业务路由。
- **Drivers**：真实数据隔离、复用已验证 CloudBase 契约、避免新增服务端 Session Store。
- **Alternatives considered**：
  - Option A：选择。最小复用现有架构。
  - Option B：拒绝当前采用。HttpOnly Cookie 更强但需要 Session Store、CSRF 和跨域 Cookie，超出本切片。
- **Why chosen**：现有服务端验证、状态门禁和 RLS 已经通过虚构账号验证；Bearer 模式只需补齐 Web SDK 和统一依赖即可形成最短闭环。
- **Consequences**：
  - 正面：业务层只处理内部 UUID；静态 Web 与 API 可独立部署。
  - 负面：浏览器会话安全依赖 SDK 与 XSS 防护；每次 API 请求增加 CloudBase 校验和状态查询。
- **Follow-ups**：公开邮箱注册、密码找回、完整账号注销、Chat 标准方舟迁移、认证监控与告警。

## Architect challenge

### Steelman against Option A

最强反对意见是：浏览器 Bearer Token 扩大 XSS 影响面，并且每请求双远程校验会增加延迟和可用性耦合。如果 Dayfold 已准备长期运营，BFF Cookie 能更集中地控制 Session。

若该反驳成立，应切换 Option B，并接受新增 Session Store、CSRF、Cookie Domain 和刷新 Token 加密存储。当前阶段没有这些基础设施，直接采用 BFF 会推迟可验证闭环，因此保留为后续安全升级。

### Tradeoff tensions

- 客户端 Token 暴露面 vs 最小架构改动：用 SDK 管理、严格 CSP 和无动态 HTML 注入约束风险。
- 每请求实时状态门禁 vs 延迟：安全优先，不缓存 `active` 状态。
- 公开注册完整度 vs 私测交付速度：首版受邀账号，公开注册需独立风控和防滥用 Gate。

## Critic verdict

| 维度 | 状态 | 备注 |
|---|---|---|
| Principle consistency | ✓ | 内部 UUID 与 fail-closed 贯穿所有步骤 |
| Alternative exploration | ✓ | Bearer 与 BFF 为真实不同架构 |
| Risk mitigation | ✓ | 每项风险均有对应测试或边界 |
| AC testability | ✓ | AC 均有 HTTP、单测或双账号 E2E 证据 |
| Verification concreteness | ✓ | 命令与状态码明确 |
| File coverage | ✓ | 实施步骤均绑定具体文件或平台配置 |
| Pre-mortem | ✓ | 覆盖映射、越权、SDK 初始化和供应商故障 |
| Expanded test plan | ✓ | Unit / Integration / E2E / Observability 完整 |

### Verdict: APPROVED

### Reservations

- `apps/web/package.json` 引入构建链会改变当前零构建静态部署；Phase 4 必须先在 Preview 验证 Vercel 输出目录和缓存策略。
- 首版暂缓注销意味着只能称为“受邀正式账号私测”，不能开放公众注册或宣称完整公开服务。
- Chat 仍使用 Agent Plan，账号闭环通过不等于 AI 可用性达标。

## Review trail

- Planner draft v1：提出 SDK Bearer 与 BFF Cookie 两个方案，初选 SDK Bearer。
- Architect challenge v1：指出内部 UUID 映射来源、SDK 重复初始化和公开注册范围未闭合。
- Critic verdict v1：REVISE，要求明确受邀账号边界、RLS 列权限、Demo 数据处置和双账号 E2E。
- Planner draft v2：补齐 `users.id` 映射、受邀账号预置、Demo 清理、逐路由鉴权矩阵与回滚。
- Architect challenge v2：保留客户端 Token 和双远程校验的架构风险。
- Critic verdict v2：APPROVED，附三项保留意见。
- Runtime verification：CloudBase 控制台的 JS SDK 2.32 快速开始仅使用 `env` 与
  `region`，且当前环境无 Publishable Key 配置入口；实现据此删除空 `accessKey`，
  该变更由前端契约测试覆盖。
- Final iterations: 2 / 3
