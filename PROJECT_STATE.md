# Dayfold Project State

更新时间：2026-09-25  
当前模式：Portfolio MVP Acceleration  
当前位置：Portfolio MVP / Step 9 — Deployment / Full AI E2E Passed

## 当前目标

尽快交付可在线访问、可真实交互的 AI Memory Demo。完成标准是：

```text
Today → Chat → Memory Extraction → Embedding → Vector Retrieval
→ AI Recall → Evidence-based Growth
```

Demo 只使用固定合成用户和虚构数据。页面必须显示：

> Demo only. Do not enter sensitive personal information.

## 当前事实

- 现有 FastAPI 提供健康检查和 CloudBase Auth 状态探针。
- Demo Mode 基础契约已实现，默认关闭，通过 `DAYFOLD_DEMO_MODE=true` 启用。
- Demo Mode 使用固定合成用户，不开放真实用户注册。
- Today Entry 已实现创建、列表、读取、按版本编辑和软删除。
- Today Entry 当前使用 SQLite Repository 完成本地真实持久化和租户隔离。
- Chat 已实现会话创建、多轮消息持久化和方舟 SSE 流式回复。
- Memory Extraction 已支持 Entry 和用户 Chat Message 来源，输出只允许 Event、
  Interest、Goal，并在校验后原子保存 Memory 与来源关系。
- Active Memory Embedding 与租户内 Vector Retrieval 已完成代码和本地契约测试。
- Chat 已自动同步 Active Memory Embedding、执行租户内检索并注入相关上下文。
- “最近的你”已基于当前用户 Active Memory 和不同来源生成，并保存证据关系。
- Memory Control 已支持查看、来源追踪、Disable 和确定性删除。
- Web 已升级为可交互 Portfolio Demo，串联 Today、Chat、Memory 和 Growth。
- 数据连接层已支持本地 SQLite 与远程 Turso，线上不会依赖容器临时文件。
- 现有生产级 Auth 工作保留但不再是 Portfolio MVP 的前置条件。

## Critical Path

1. Foundation
2. Today CRUD
3. LLM Chat with streaming
4. Event / Interest / Goal extraction
5. Embedding and vector retrieval
6. Memory-aware recall
7. Evidence-based “最近的你”
8. Visual polish and mobile states
9. Online deployment and end-to-end demo validation

## 当前任务

Task 1 已完成：Demo Mode 基础契约。

Task 2 已完成：Today Entry 数据库 Schema、Repository 和 CRUD API。

Task 3 已完成：真实 LLM 多轮 Chat 与 SSE Streaming。

Task 4 已完成：从 Entry 和 Chat Message 提取 Event、Interest、Goal，
完成严格校验、来源绑定和持久化。

Task 5 代码已完成：为 Active Memory 生成 Embedding，并按租户、状态、模型和维度
执行精确 cosine retrieval。

真实在线验证已完成：标准方舟接口生成两条 1024 维向量，检索结果按 cosine score
降序返回，与职业方向相关的 Goal 排名第一。

Task 6 已完成：Chat 在生成前自动检索相关 Active Memory，组装可追溯上下文。
真实 Vertical Slice 已验证日记生成 Goal、向量召回和 AI 回忆过去职业方向。

Task 7 已完成：基于真实历史 Memory 与来源生成“最近的你”；证据不足时返回
“正在积累你的记录。”，不调用模型。

Memory Control 已完成：Disable 立即移除向量；Delete 清理来源、Embedding 和失效的
Growth 引用，所有操作强制绑定当前用户。

Step 8 已完成并按参考风格修订：Web 统一为 Preview 同源的蓝色横线纸、手写字体和
单列轻量界面，移除侧栏、卡片与厚重视觉层；桌面与移动端 Loading/Error 状态、
SSE 流式显示、Memory 控制和 Growth 证据展示均已接入真实 API。

Step 9 持久化边界已完成并通过真实远程验证：线上必须显式配置
`DAYFOLD_DATA_BACKEND=turso`、`TURSO_DATABASE_URL` 和 `TURSO_AUTH_TOKEN`；
凭证缺失时不会回退本地 SQLite。独立连接持久化验证脚本已加入。

远程 Turso Portfolio Demo 数据库已创建；URL 和 Token 仅保存于 macOS 钥匙串。
真实 smoke test 已完成跨连接写入、读取和清理，结果为 `passed`。

CloudBase Run API 已部署至 `dayfold-api-probe`，线上版本 `005` 承载 `100%`
流量。Turso、Ark、Demo Mode 和 CORS 共 10 个环境变量仅在服务端配置并掩码显示。

在线持久性验证已完成：版本 `004` 创建合成 Entry，重新部署并切换到版本 `005`
后仍以同一 ID 读取成功；测试记录随后已软删除并确认返回 `404`。

Web 已重新发布到 `https://www.dayfold.com.cn`。`https://dayfold.com.cn` 继续
通过 HTTPS 308 跳转至 `www`；线上 `app.js` 已确认只使用
`https://dayfold-api-global.vercel.app`，不再引用失效的 CloudBase 自定义域名。

CloudBase HTTP 网关已添加 `/` 路由并关联 `dayfold-api-staging`。为
`api.dayfold.com.cn` 申请的腾讯云 SSL 证书已签发，域名所有权 TXT 验证也已通过；
但腾讯云备案控制台确认 `dayfold.com.cn` 状态为“未备案”，CloudBase 自定义域名
因此保持“失败”且未生成有效 CNAME。测试域名仍被访问量上限拦截，Web 已不再使用
该 CloudBase 地址。

部署决策已调整：`dayfold.com.cn` 注册于腾讯云，但现有 `www.dayfold.com.cn`
Vercel Web 和腾讯云 DNS 保持不变；Portfolio MVP 不以 ICP 备案为前置条件。API
迁移到独立海外平台项目，先使用平台默认 HTTPS 域名。

Vercel FastAPI 独立部署适配已加入仓库根目录，包含 `app.py`、根级
`requirements.txt` 和 `vercel.json`。适配测试及 API 全量测试通过，共
`107 passed`；Python 编译与 `git diff --check` 通过。

独立海外 API 项目 `dayfold-api-global` 已创建，Production 环境已配置 Turso、
Ark、Demo Mode、CORS 和召回阈值等 10 项变量；敏感值由 macOS 钥匙串直接注入，
未写入源码或命令参数。稳定默认地址为
`https://dayfold-api-global.vercel.app`。线上 `/health`、`/v1/demo` 和
`/v1/entries` 均返回 `200`，且 CORS 正确允许 `https://www.dayfold.com.cn`。

Vercel Function 已固定到香港 `hkg1`，Function 上限为 `180s`。Memory 与 Growth
已切换到标准方舟 OpenAI 兼容推理端点
`/api/v3/chat/completions`，使用独立标准 Ark Key 与在线推理 Endpoint ID；
Chat 暂时继续使用 Agent Plan。

Memory、Growth 和 Chat Provider 已接入统一错误分类与有界重试：
最多 2 次，仅 timeout、network、`429`、`5xx` 重试；auth 和 request rejected
立即失败。单次 Provider 窗口为 `80s`，API/SSE 可区分 `LLM_TIMEOUT`、
`LLM_RATE_LIMITED`、`LLM_AUTHENTICATION_FAILED`、`LLM_REQUEST_REJECTED`、
`LLM_UPSTREAM_ERROR` 和 `LLM_UNAVAILABLE`。

标准方舟切换后的完整线上 E2E 已通过：创建 2 条虚构 Today Entry，提取 2 条
Memory，写入 2 个 Embedding，Recall 命中 2 条本次 Memory，Growth 以 2 条本次
Memory 作为证据生成 `ready` 结果。验收脚本在 `finally` 中删除全部测试 Memory
与 Entry，并确认本次创建记录残留为 0。详细诊断见
`.claude/artifacts/fixes/agent-plan-resilience.md`。

下一任务：进行上线后的交互巡检与作品集交付整理；Chat 的 Agent Plan 路径继续
保留现有错误分类和有界重试，后续可按稳定性数据决定是否迁移。

## 安全边界

- API Key 仅存在于服务端环境变量。
- 所有业务数据访问必须由服务端绑定固定 Demo User；客户端不能提交或覆盖 `user_id`。
- Demo 只使用虚构或 seeded 数据。
- Memory 删除和 Disable 必须确定性执行，不交给 LLM 判断。
- Growth 必须引用真实历史来源；证据不足时返回“正在积累你的记录。”

## POST-MVP BACKLOG

- 完整注册、邮件验证和密码找回
- 多设备生命周期和完整账户中心
- 数据导出和完整账户注销
- 复杂后台、监控、备份恢复和 CI/CD
- PWA、Native App、Subscription、Community、Notification
- 多模型路由
- Emotional、Relationship、Personality Memory
- 完整 Life Timeline 和复杂 Themes
