# Dayfold Project State

更新时间：2026-10-09
当前阶段：Portfolio MVP / Phase 10 — Post-launch Stabilization
状态：公开 Demo 已上线；主链路已实现；Growth 生产调用仍有阻断问题

## 文档定位

本文件是 Dayfold **当前项目状态的唯一事实源**。

- [`README.md`](README.md)：面向公开访问者的简要介绍。
- `docs/p0` 至 `docs/p4`：对应日期的设计、评审和交付快照。
- `.claude/artifacts/`：修复、QA 和决策证据。
- 仓库中不存在 `MASTER.md`；后续不再使用该名称描述当前状态。

历史文档中的测试数量、架构方案和部署结论不得覆盖本文件的最新状态。

## 当前目标

交付可在线访问、可真实交互、仅使用合成数据的 AI Memory Portfolio Demo：

```text
Today → Memory Extraction → Embedding → Vector Retrieval
→ Memory-aware Chat → Evidence-based Growth
```

当前优先级不是继续扩展功能，而是修复 Growth 生产稳定性，并维持数据清理、
隐私边界和可复现验证。

## 生产入口

| 入口 | 地址 | 当前状态 |
| --- | --- | --- |
| Web | `https://www.dayfold.com.cn` | HTTP 200 |
| API | `https://dayfold-api-global.vercel.app` | 已部署 |
| Health | `https://dayfold-api-global.vercel.app/health` | HTTP 200 |
| Demo contract | `https://dayfold-api-global.vercel.app/v1/demo` | HTTP 200 |

部署架构：

- Web：Vercel 静态 HTML/CSS/JavaScript。
- API：Vercel FastAPI，区域固定为 `hkg1`，函数上限 `180s`。
- 数据库：生产 Turso，本地 SQLite。
- AI：火山方舟；Chat 使用 Agent Plan，Memory/Growth 使用标准推理 Endpoint。

`/health` 当前返回的 `environment: preview` 与 `version: p1-probe` 是早期探针遗留
命名，不代表当前发布阶段，后续应单独修正。

## 模块状态

| 模块 | 状态 | 已验证能力 |
| --- | --- | --- |
| Demo Mode | 可用 | 固定合成用户、隐私提示、默认关闭 |
| Today | 可用 | Entry 创建、列表、读取、版本编辑、软删除 |
| Chat | 可用 | 多轮持久化、SSE、相关 Memory 注入 |
| Memory Extraction | 可用 | Event/Interest/Goal、来源绑定、顺序重试幂等 |
| Embedding | 可用 | 1024 维向量、Active Memory 同步 |
| Retrieval | 可用 | `user_id` 绑定、cosine 排序、阈值 `0.30` |
| Memory Control | 可用 | 查看来源、Disable、确定性 Delete |
| Growth | 代码完成，生产阻断 | 证据门槛和持久化已实现；Provider 生产请求持续 `504` |
| Auth | 非公开主路径 | 代码和 Preview 验证保留；公开站点仍为合成 Demo User |

## 当前验证基线

本轮重新执行：

```text
API tests: 110 passed
Python compileall: passed
git diff --check: passed
```

已有生产证据：

- Web、`/health`、`/v1/demo` 可访问。
- Today、Memory Extraction、Embedding、Vector Retrieval、Recall 已完成真实链路
  验证。
- Memory Extraction 同一来源重试返回相同 Memory ID，不重复写入。
- 测试 Entry 与 Memory 在验收后均执行清理。

历史文件中出现的 `107 passed`、`108 passed` 是当时快照；当前基线统一为
`110 passed`。

## 当前阻断：Growth Provider

已确认事实：

1. 相同标准方舟 Key、模型和完整 Growth Prompt 在本机连续 5/5 成功，耗时
   8.7–18.6 秒。
2. 生产环境使用两次非流式请求时连续 10/10 返回 `504 LLM_TIMEOUT`，每次约
   22.3 秒。
3. 增加第三次重试后仍连续 10/10 返回 `504`，只把失败时间延长到约 33.4 秒；
   该改动已撤销。
4. 提交 `3c47abd` 已将 Growth 改为 `stream=true` 并部署成功，但生产隔离验证
   仍 3/3 返回 `504`，每次约 22.3 秒。
5. 流式请求没有收到可用 SSE 首包，说明问题发生在应用聚合响应之前。
6. 最新生产测试的合成 Memory 已全部删除，标记残留为 0，Growth 回到
   `collecting`。

当前结论：

- Growth 的业务规则、证据查询和流式协议单元测试通过；当前流式版本的本机真实直连
  尚未完成。
- 单纯增加重试或切换 `stream=true` 均未修复 Vercel → 方舟生产链路。
- 在获得新的根因证据前，不应把 Growth 标记为生产可用。

## 最近关键提交

| Commit | 说明 | 当前结论 |
| --- | --- | --- |
| `61805d2` | Memory Extraction 中文错误与幂等重试 | 保留 |
| `388d87c` | Memory 对瞬时方舟失败增加第三次尝试 | 保留 |
| `addef50` | Growth 第三次重试实验 | 无效 |
| `b5bef36` | 撤销 Growth 第三次重试 | 保留 |
| `3c47abd` | Growth 改为 `stream=true` | 已部署，生产仍 `504` |

## 下一步

1. 从 Vercel Runtime Logs 获取 Growth 上游响应状态、请求 ID 和方舟错误体，确认
   `LLM_TIMEOUT` 是方舟 `5xx`、网关超时还是流读取超时。
2. 在方舟控制台核对当前 Endpoint 的模型类型、首包延迟、区域路由和监控记录。
3. 若同一 Endpoint 在 Vercel 链路持续失败，为 Growth 创建独立低延迟 Endpoint；
   不再继续增加重试次数。
4. 根因修复后执行至少 3 次隔离生产 Growth 验证，并确认测试 Memory 残留为 0。
5. 单独修正 `/health` 的遗留环境与版本字段。

## 安全边界

- 公开 Demo 只使用固定合成用户和虚构数据。
- 所有业务查询必须绑定 `user_id`。
- API Key 只存于服务端环境变量或 macOS 钥匙串。
- Memory 仅允许 Event、Interest、Goal。
- Growth 至少需要两条 Memory，且来自两个不同来源。
- Disable Memory 时删除 Embedding；Delete 时清理来源、Embedding 和失效 Growth
  引用。
- 生产 Turso 凭证缺失时禁止回退到临时 SQLite。

## POST-MVP

- 正式公开注册、密码找回和账户中心。
- 完整多租户公开发布与数据导出/注销。
- 监控、告警、备份恢复和正式 CI/CD。
- 多模型路由与自动降级。
- PWA、Native App、Subscription、Community、Notification。
