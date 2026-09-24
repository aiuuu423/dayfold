# Dayfold Production Readiness Review

状态：P2 GO / PRODUCTION NO-GO  
评审日期：2026-09-22  
评审对象：中国大陆正式公网 Web MVP  
当前代码基线：P1 Probe

## 评审结论

Dayfold 可以进入 P2 Technical Specification，但不具备生产发布条件。

```text
P2 Technical Specification: GO
MVP Implementation: NOT STARTED
Staging With Synthetic Data: NOT READY
Public Beta With Real Users: BLOCKED
General Availability: BLOCKED
```

P1 已证明网络、容器、数据库、向量扩展和基础身份登录路径可运行。正式上线仍缺少业务实现、租户隔离、数据生命周期、恢复演练、运行指标、备案资源和 AI 服务合规证据。任何一个涉及私人日记、聊天或长期记忆的数据边界缺口，均不能作为上线后补项。

## 影响分类

| 维度 | 是否适用 | 当前判断 | 评审边界 |
|---|---|---|---|
| 外部承诺 | 是 | 正式公网会形成对用户的可用性、隐私与删除承诺 | 没有发布批准 |
| 用户关键性 | 是 | 登录、保存、删除和 AI 回复失败会直接影响用户私人内容 | P2 只定义目标，不声明达标 |
| 数据敏感度 | 高 | 日记、聊天、记忆、目标和身份信息均为私人数据 | 无真实用户数据许可 |
| 状态持久性 | 高 | 原始内容、派生记忆、向量和删除关系需要长期一致 | 没有恢复演练 |
| 爆炸半径 | 中高 | 单租户错误可泄漏私人内容，平台错误可影响全部用户 | 跨用户访问容忍度为零 |

## 就绪矩阵

| 领域 | 状态 | 证据 | 新鲜度与漂移 | 阻断 |
|---|---|---|---|---|
| 产品范围 | Pass | `docs/mvp/Life-Companion-MVP-Specification.md` | 2026-09-11，需在 P2 复核命名和页面范围 | 否 |
| 架构方向 | Pass | `docs/p2/dayfold-p2-technical-specification.md` | v1.0 已冻结 O-01 至 O-10 | 否 |
| Preview 网络 | Pass | `docs/p1/minimal-deployment-probe-result.md` | Vercel + Render 验证有效，但不代表 Production | 否 |
| CloudBase 技术路径 | Pass | `docs/p1/cloudbase-free-environment-validation-result.md` | 2026-09-22，已取得工单 `202609226778` 人工答复 | 否 |
| 正式 Web | Blocker | `apps/web/` 只有静态 Probe | 没有 React/Vite 产品实现 | 是 |
| 正式 API | Blocker | `apps/api/main.py` 只有 `/health` | 没有账户、Journal、Chat 或 Memory API | 是 |
| Auth | Blocker | CloudBase 用户名登录技术验证 | 无服务端 Token 校验、恢复登录和注销闭环 | 是 |
| PostgreSQL Schema | Blocker | 无业务迁移文件 | 无正式表、约束、RLS 或删除任务设计 | 是 |
| Tenant Isolation | Blocker | 仅有原则，无执行证据 | 没有双用户负向测试 | 是 |
| Memory Lifecycle | Blocker | P1 评测与 Prompt 已通过 | 没有生产存储、来源、纠正和删除传播 | 是 |
| Backup / Restore | Blocker | 无恢复报告 | 没有 RPO、RTO 或实际恢复演练 | 是 |
| Observability | Blocker | 云平台存在基础日志 | 无用户旅程指标、告警和 Runbook | 是 |
| Capacity | Blocker | 仅验证单次 `/health` | 无注册、AI、数据库和 Worker 负载测试 | 是 |
| Safe Change | Follow-up | Preview 部署和版本切换可用 | 无生产迁移、灰度、回滚演练 | 公测前 |
| Secrets | Follow-up | 约束禁止写入源码 | 无生产 Secret 清单、轮换与权限审查 | 公测前 |
| ICP / 域名 | Blocker | `docs/p1/dayfold-production-launch-stage-and-operations.md` | 当前免费资源不满足备案路径 | 是 |
| AI 合规 | Blocker | 已识别标识、安全评估和备案判断 | 尚无专业结论或控制证据 | 是 |
| 隐私与协议 | Blocker | MVP 规格列出页面 | 尚无可发布政策文本和第三方处理者清单 | 是 |
| 事故响应 | Blocker | 无 Runbook | 无负责人、关闭开关、通知或复盘流程 | 是 |

## 责任

| 领域 | Owner | 升级路径 | Ready | 证据 |
|---|---|---|---|---|
| 产品与发布决定 | Dayfold 项目负责人 | 暂停发布并回到 P2 评审 | 部分 | 当前阶段文档 |
| 应用与数据 | Dayfold 工程负责人 | 停止写入、回滚版本、恢复数据 | 否 | 尚无生产 Runbook |
| 云平台 | 腾讯云 CloudBase | 人工工单与平台支持 | 部分 | 工单 `202609226778` |
| 模型服务 | Provider owner 待冻结 | 关闭 AI、切换 Provider 或降级 | 否 | Provider adapter 仅为架构方向 |
| 合规与隐私 | 待指定 | 法律/合规专业意见 | 否 | 尚无正式评估 |
| 事故响应 | 待指定 | 关闭注册、AI 或 Memory 写入 | 否 | 尚无值守和沟通路径 |

生产发布前必须把“待指定”替换为真实负责人或明确自动化路径。

## 架构与故障域

| 组件 | 生产依赖 | 故障域 | 当前证据 |
|---|---|---|---|
| Web | 静态托管、DNS、TLS | 前端托管平台、公共网络 | Preview Probe |
| API | FastAPI 容器、HTTP 网关 | CloudBase 上海单地域 | `/health` 版本 `002` |
| Auth | CloudBase Auth | CloudBase 身份服务 | 用户名登录 JWT Probe |
| Database | PostgreSQL + pgvector | CloudBase 上海数据库 | SQL 与向量 Probe |
| Worker | Python 异步任务 | 未部署 | 架构方向 |
| Model Provider | Ark / 可替代 Provider | 外部模型 API、配额、内容安全 | P1 评测 |
| Email | CloudBase 内置邮件代发 | CloudBase Auth | 方案已冻结，Staging 送达测试未执行 |
| Monitoring | 平台日志 + 应用指标 | 监控平台 | 未设计 |

当前关键路径：

```text
Browser
  → DNS / TLS
  → Web
  → FastAPI
  → CloudBase Auth
  → PostgreSQL / pgvector
  → Worker
  → Model Provider
```

生产依赖均集中在上海单地域是可接受的 MVP 成本选择，但不能宣称区域级高可用。必须具备数据库备份恢复、Provider 降级和停止写入能力。

## 用户旅程与 SLO

| 用户旅程 | P2 需要冻结的目标 | 当前证据 | 发布风险 | 状态 |
|---|---|---|---|---|
| 注册与登录 | 成功率、p95、恢复登录 | 仅虚构用户名登录 | 用户无法进入或无法找回账户 | Blocker |
| 保存日记 | 原始内容不因 AI 失败丢失 | 无业务 API | 私人记录丢失 | Blocker |
| AI 对话 | 首 Token、完成率、超时降级 | 仅模型评测延迟 | 卡死、重复消息、错误保存 | Blocker |
| Memory 提取 | 异步成功率、积压和重试 | 离线评测通过 | 记忆遗漏或重复 | Blocker |
| Memory 召回 | 相关性、来源和租户过滤 | 无生产检索 | 错误或跨用户召回 | Blocker |
| 删除与注销 | 删除完成时限和失败重试 | 无 E2E 证据 | 删除后继续召回 | Blocker |

当前没有生产流量，错误预算为“不适用”。公测前必须定义 SLO 并通过 Staging 产生基线；没有基线时不能宣称错误预算充足。

## 可观测性

| 信号 | Dashboard / Alert | 缺失信号时的处理 | Owner | Ready |
|---|---|---|---|---|
| Web 可达与核心页面 | 未建立 | 停止扩大流量 | 待指定 | 否 |
| API 错误率与延迟 | 未建立 | 回滚或停注册 | 待指定 | 否 |
| Auth 成功与异常 | 未建立 | 禁止继续放量 | 待指定 | 否 |
| DB 连接、慢查询和存储 | 未建立 | 停止写入并检查数据库 | 待指定 | 否 |
| Worker 积压和重试 | 未建立 | 暂停 Memory 任务 | 待指定 | 否 |
| Provider 错误、限流和成本 | 未建立 | 降级为保存原文、不生成 | 待指定 | 否 |
| 删除任务失败 | 未建立 | 冻结相关账户并人工处置 | 待指定 | 否 |

P2 已在技术规格中冻结指标与 SLO；P3 实现 Dashboard、告警和通知接收人。

## 安全变更

| 变更路径 | 发布、停止与回滚证据 | 是否演练 | 缺口 |
|---|---|---|---|
| Web 发布 | Vercel Preview 可部署 | 部分 | 无正式域名与生产回滚记录 |
| API 发布 | CloudBase 版本 `001 → 002` 成功 | 部分 | 无业务兼容性和自动回滚 |
| Schema 迁移 | 无 | 否 | 需要 expand / migrate / contract 规则 |
| Auth 配置 | 控制台手工验证 | 否 | 需要配置版本、回调与撤销路径 |
| Provider 切换 | Adapter 为设计原则 | 否 | 需要超时、重试、熔断和降级 |

正式上线前必须保证应用回滚不会依赖不可逆 Schema 回滚。

## 可用性与恢复

| 故障域独立性 | 丢失故障域后的静态能力 | 恢复机制 | 演练结果 |
|---|---|---|---|
| 单地域、单云服务商 | 无跨地域热备 | 数据库备份 + 重建应用 | 未演练 |
| Model Provider 可隔离 | 应保存原始内容并返回明确失败 | 重试或切换 Provider | 未实现 |
| Web 与 API 可独立回滚 | Preview 已分离 | 版本回退 / DNS 回退 | 只验证基础部署 |

MVP 不要求跨地域双活。数据库恢复演练、原始内容优先保存和 Provider 降级是生产阻断项。

## 安全与完整性

| 领域 | 证据 | 残余风险 | 分类 | Owner |
|---|---|---|---|---|
| CORS | 白名单与未知 Origin 负向验证 | 正式 Origin 已冻结，Production 尚未配置 | Follow-up | 工程负责人 |
| Secret | 文档约束和环境变量原则 | 无生产清单与轮换 | Blocker | 工程负责人 |
| Tenant Isolation | `user_id` 强制原则 | 无双用户 E2E 证据 | Blocker | 工程负责人 |
| Input Validation | FastAPI 尚无业务输入 | 注入、越权和大文本风险未建模 | Blocker | 工程负责人 |
| Data Lifecycle | 删除原则已定义 | 无派生数据删除传播 | Blocker | 产品 + 工程 |
| LLM Safety | P1 评测与内容安全方向 | Prompt 注入、越权检索和敏感输出未评测 | Blocker | AI 工程负责人 |
| Supply Chain | 依赖使用版本范围 | 无锁定、SBOM 或漏洞门禁 | Blocker | 工程负责人 |

## 发布阻断项

| 阻断项 | 证据路径 | 解除条件 | 到期门槛 |
|---|---|---|---|
| 正式产品未实现 | `apps/web/`、`apps/api/` | MVP 最小纵切完成 | Staging 前 |
| Auth 生产闭环缺失 | CloudBase Auth Probe | 服务端校验、恢复登录、撤销和注销通过 | 公测前 |
| Tenant Isolation 未验证 | 尚无测试 | 双用户负向测试全部通过 | 公测前 |
| 删除传播未验证 | 尚无 E2E | 原始、派生、向量和任务删除一致 | 公测前 |
| 备份恢复未演练 | 尚无报告 | 完整恢复演练达到 RPO/RTO | 公测前 |
| SLO 与告警未实现 | `docs/p2/dayfold-p2-technical-specification.md` | 核心旅程 Dashboard、告警和 Runbook 生效 | 公测前 |
| 容量证据缺失 | 尚无负载报告 | 目标并发和峰值测试通过 | 公测前 |
| 备案资源尚未购买 | P2 技术规格 O-07 | 人工确认主体一致性后，购买上海轻量应用服务器并提交 ICP | ICP 申请前 |
| ICP 未完成 | 无备案号 | 获得备案号并展示 | 正式域名开放前 |
| AI 合规结论缺失 | 无正式评估 | 标识、安全评估、算法/生成式 AI 备案责任有书面结论 | 公测前 |
| 隐私政策与协议缺失 | 无发布文本 | 政策、协议、第三方清单与同意流程通过评审 | 公测前 |
| 事故响应缺失 | 无 Runbook | 负责人、停服开关、通知和复盘路径完成演练 | 公测前 |

## 例外登记

当前没有接受任何生产例外。

| 例外 | 风险 | 补偿控制 | Owner | 到期 | 接受人 |
|---|---|---|---|---|---|
| 无 | 无 | 无 | 无 | 无 | 无 |

Preview 环境继续使用虚构数据不是生产例外，因为它不接收真实用户、不形成生产承诺，也不替代任何发布阻断项。

## 上线观察与交接

| 观察窗口 | 成功检查 | 中止检查 | 响应交接 |
|---|---|---|---|
| 公测前 24 小时 | 备份、迁移、核心旅程和告警演练通过 | 任一阻断项未关闭 | 不开放注册 |
| 公测后 0–2 小时 | 注册、保存、AI、Memory、删除健康 | 越权、丢数据、持续 5xx 或任务堆积 | 停止注册和 AI / Memory 写入 |
| 公测后 2–24 小时 | 错误率、p95、成本和投诉稳定 | 错误预算快速消耗或恢复失败 | 回滚应用并保留数据 |
| 公测后 1–7 天 | 删除完成率、Memory 准确性和恢复能力 | 删除失效、跨用户访问、严重内容安全事件 | 停止公测 |

发布 Owner、回滚 Owner 和响应人必须在 P4 前实名记录。当前全部视为未就绪。

## P2 第一批任务

P2 从设计与验证开始，不从 UI 开发开始：

1. 冻结 CloudBase Auth 服务端验证、内部用户映射和账户删除契约。
2. 冻结 PostgreSQL Schema、`user_id` 约束、来源关系和删除传播。
3. 冻结同步 API、异步 Worker、幂等键、重试和失败状态。
4. 冻结 Preview、Staging、Production 的资源与 Secret 边界。
5. 定义核心旅程 SLO、日志字段、告警和停止开关。
6. 定义备份、恢复、Schema 迁移和灾难恢复演练。
7. 取得备案资源路径与 AI 服务合规的书面结论。

第一项实现前的交付物应为：

```text
docs/p2/dayfold-p2-technical-specification.md
```

该规格通过评审后，才初始化 React/Vite 产品应用和 FastAPI 模块化业务后端。

## 优先跟进

| 方向 | 原因 | 优先级 |
|---|---|---|
| Identity + Tenant Isolation | 私人数据系统的跨用户访问容忍度为零 | P0 |
| Backup + Data Lifecycle | 删除与恢复必须同时可证明 | P0 |

## 决策边界

本评审可以标记客观阻断项，不能替项目负责人作出接受生产风险的决定。

当前建议：

```text
继续 P2：YES
购买生产资源：NO
创建正式 Schema：NO
接入真实用户数据：NO
开放 Public Beta：NO
切换正式 DNS：NO
```
