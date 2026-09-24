# Dayfold P1 Final Architecture Decisions

状态：部署地域已冻结，正式身份方案等待成本裁决  
日期：2026-09-21  
当前阶段：P1 Closeout  
适用范围：正式部署地域、备案路径、Preview 边界与 P2 进入条件

## 当前结论

Dayfold 正式生产环境采用中国大陆备案部署路径，主地域冻结为中国大陆华东（上海）。腾讯云作为首选备案接入商和首个正式基础设施候选；Frontend、FastAPI、PostgreSQL 与 Python Worker 原则上部署在同一地域。

现有 Vercel 与 Render 环境继续保留为 P1 Preview，只使用虚构或脱敏数据。它们不升级为 Dayfold 正式生产环境，也不保存 Journal、Chat、Memory、Growth 或用户资料。

部署地域与环境边界已经冻结。Tencent OneID 已因高固定成本退出 P1 / MVP 候选；Authing 免费账户验证只通过 OIDC Discovery、JWKS 和用户状态管理；腾讯云上海自托管 Logto 虽能控制数据地域，但官方最低资源和单人运维负担不符合当前轻量目标。正式 Managed Auth、正式入口域名和具体云产品规格仍需分别裁决，因此 P1 尚未完整结束。

## 决策状态

| 决策 | 状态 | 结论 |
|---|---|---|
| 正式部署路径 | 已冻结 | 中国大陆备案部署 |
| 主部署地域 | 已冻结 | 中国大陆华东（上海） |
| 首选备案接入商 | 已冻结 | 腾讯云 |
| 正式技术方向 | 保持 | React/Vite + FastAPI + PostgreSQL/pgvector + Python Worker |
| 生产数据地域 | 已冻结 | 与 API、Worker 保持中国大陆同地域 |
| Preview 环境 | 已冻结 | Vercel + Render，仅用于无真实数据验证 |
| Managed Auth | 等待成本裁决 | Tencent OneID、Authing 免费计划均不采用；Logto 有条件可行但不批准部署，先取得腾讯云长期报价 |
| 正式入口域名 | 待裁决 | ICP 备案通过前不启用根域名或 `www` 正式入口 |
| 具体云产品规格 | 延后到 P2 Technical Specification | 不在 P1 提前购买或锁定实例规格 |

## 决策依据

### 中国大陆备案路径

Dayfold 的目标用户和主要访问网络位于中国大陆。P1 Preview 已证明 Vercel、Render、HTTPS、CORS 和三网基础可达性，但 309 个节点中仍有 15 个失败，Render Free 冷启动也曾超过 Web 当前 10 秒超时。这些结果足以证明公网链路可行，不足以把境外免费平台冻结为正式生产拓扑。

腾讯云规定，网站托管在腾讯云中国大陆地区云服务器并对外提供服务时，需要在开通服务前完成 ICP 备案。首次备案需要准备实名认证账号、备案域名、符合条件的备案云资源和主体材料，最终要求以主体所在省通信管理局规则为准。[腾讯云首次备案说明](https://cloud.tencent.com/document/product/243/37402)

用于备案的腾讯云 CVM 或轻量应用服务器需要位于中国境内、具有公网 IP，并满足包年包月及购买时长要求。当前官方规则要求购买时长达到三个月及以上，备案期间剩余有效期不少于一个月。[腾讯云备案云资源说明](https://cloud.tencent.com/document/product/243/18908)

### 华东（上海）主地域

华东（上海）作为 Dayfold 首个正式主地域，理由如下：

- 面向全国个人用户，不把生产系统绑定到当前开发者所在地。
- Frontend、API、数据库和 Worker 可以保持同地域，减少跨地域调用和数据复制。
- 腾讯云可同时承担备案接入、计算和托管 PostgreSQL 候选，降低单人项目的运维边界。
- Preview 与生产使用不同域名和不同数据边界，迁移可以逐步完成，不需要一次替换现有验证环境。

主地域是架构默认值，不代表允许自动购买资源。P2 Technical Specification 必须先核对目标产品在上海地域的可用区、规格、备份、价格和配额，再决定具体实例。

### PostgreSQL 与向量能力

PostgreSQL 继续作为 Dayfold 业务事实来源，Memory 元数据、来源关系、删除状态和向量保持同一数据边界。腾讯云数据库 PostgreSQL 已提供 `pgvector` 插件，支持向量类型、余弦距离、HNSW 与 IVFFlat 索引；具体 PostgreSQL 和内核版本必须在创建实例前按官方支持矩阵核对。[腾讯云 PostgreSQL pgvector 文档](https://cloud.tencent.com/document/product/409/138219)

这项能力证明腾讯云可以作为正式数据库候选，但不构成提前创建数据库的授权。Schema、迁移、索引和备份策略仍属于 P2 Technical Specification。

## 正式环境边界

正式环境采用以下逻辑拓扑：

```text
中国大陆正式入口
        ↓ HTTPS
Frontend 静态资源 / Web
        ↓
FastAPI modular monolith
        ├── Journal
        ├── Chat
        ├── Memory
        ├── Retrieval
        └── Evaluation
        ↓
PostgreSQL + pgvector
        ↓
Python Worker
        ↓
Model Provider adapters
```

部署约束：

- Frontend、FastAPI、PostgreSQL 和 Worker 默认位于腾讯云华东（上海）。
- PostgreSQL 不开放公网写入；API 和 Worker 通过私有网络访问。
- 正式环境使用独立数据库、Secret、域名和日志，不复用 Preview 配置。
- 所有业务查询必须绑定当前 `user_id`。
- Journal、Chat、Memory、Growth 和 User profile 不进入 Vercel、Render 或 Dify。
- Dify 继续只处理版本化虚构评测数据。
- Provider 只接收当前请求所需的最小上下文，不成为业务事实来源。

## Preview 环境边界

现有 Preview 保持不变：

```text
preview.dayfold.com.cn      → Vercel
api-preview.dayfold.com.cn  → Render
```

Preview 允许：

- 展示无真实数据的静态页面。
- 验证 HTTPS、CORS 和固定 `/health`。
- 使用虚构或充分脱敏的测试数据。
- 保留平台默认域名作为独立故障排查入口。

Preview 禁止：

- 注册或登录真实用户。
- 保存真实日记、聊天或 Memory。
- 接入生产数据库。
- 接收生产 Auth Token。
- 被描述为正式产品、生产环境或中国大陆 SLA 证明。

## 域名与备案边界

ICP 备案通过前：

- `dayfold.com.cn` 根域名和 `www` 不指向正式产品。
- `preview.dayfold.com.cn` 与 `api-preview.dayfold.com.cn` 保持 Preview 标识。
- 不在备案材料、公开文档或 DNS 中伪装已经上线的产品能力。

ICP 备案通过后：

- 正式入口只能指向已完成备案接入的中国大陆资源。
- 页面按备案要求展示备案号和合规链接。
- Preview 子域名继续与正式环境隔离，不共享数据库或 Auth Secret。
- DNS 切换必须保留回滚记录，不直接删除现有 Preview 解析。

正式入口使用根域名还是 `www`，将在域名与 Auth 回调方案一起裁决。本文件不提前指定。

## 备案执行前置条件

开始备案前必须满足：

1. 腾讯云账号实名主体与备案主体一致。
2. `dayfold.com.cn` 域名实名信息符合主体要求。
3. 购买符合腾讯云备案条件的中国大陆资源。
4. 明确备案性质为个人或单位，并核对主体所在省管局要求。
5. 准备网站名称、服务内容、负责人和必要材料。
6. 正式页面只展示备案申报范围内的内容。

备案完成不等于产品可以接收真实数据。Auth、用户隔离、删除传播、隐私说明、备份和安全验证通过后，正式环境才能开放注册。

## P2 进入条件

部署地域决策完成后，P1 仍有两个阻断项：

1. Authing 最小账户验证与 Managed Auth 正式采用。
2. 正式入口域名与环境命名决策。

满足以下条件后，才能开始 P2 Technical Specification：

- Managed Auth 的供应商、数据地域、回调域名和账户删除流程已冻结。
- 正式入口、Preview、Staging 和 Production 的域名边界已冻结。
- 腾讯云备案主体与可用备案资源路径已确认。
- 正式数据库和 Worker 的同地域原则已写入技术规格输入。
- 所有 Secret 继续保存在钥匙串或部署平台环境变量中。
- P1 Memory 评测资产保持不变。

P2 Technical Specification 获得人工确认前，不初始化正式 React/Vite 产品、不创建生产数据库，也不接入真实用户数据。

## 明确不变

本次决策不改变：

- Dayfold 产品范围。
- React + Vite + TypeScript 前端方向。
- FastAPI modular monolith。
- PostgreSQL + pgvector 事实来源。
- Python Worker。
- Event、Interest、Goal 三类 Memory。
- Candidate、Active、Updated、Archived、Deleted 状态。
- 用户数据隔离、来源追溯和确定性删除规则。
- Dify 的 Baseline / Experiment / Comparison Tool 定位。
- 已通过的 Prompt、数据集、评分逻辑和历史评测结果。

## 风险

### 备案周期

备案需要平台初审、短信核验和管局审核，实际时间受主体资料和省管局要求影响。没有备案结果前，正式域名不能被视为可上线入口。

### 成本

符合备案条件的资源通常需要包年包月购买。具体价格、规格和最低成本必须在 P2 Technical Specification 前重新核对，不能从历史价格推断。

### 供应商集中

腾讯云同时作为备案接入和基础设施候选可以降低早期复杂度，也会增加供应商集中风险。Dayfold 继续使用标准 FastAPI、PostgreSQL 和 Provider adapter，避免业务逻辑依赖腾讯云专有接口。

### 地域迁移

上海地域是首个正式主地域。未来若因备案主体、成本或产品需求需要调整，迁移必须覆盖数据库备份恢复、向量索引重建、Auth 回调和 DNS 切换，不能只移动 Web 服务。

## 下一项验证

P1 Closeout 的下一项唯一自然任务是：

```text
腾讯云上海 Auth 资源正式报价
```

该任务只查询上海 CVM `2C8G/256GB`、正式 PostgreSQL 和 SES 的长期续费口径价格，不购买或部署资源。报价完成后再决定继续 Logto、接受付费托管 Auth，或延后真实用户身份功能。
