# Dayfold P1 Managed Auth 候选评估

状态：托管候选与自托管 Logto 均完成 P1 评估，正式 Auth 仍待成本裁决  
日期：2026-09-21  
当前阶段：P1 Closeout  
适用范围：正式身份源、认证协议、内部用户映射与账户删除边界

## 结论

Authing 免费账户验证确认 OIDC Discovery 与 JWKS 可用，但邮箱流程受实名认证前置条件阻断，未获得实际 ID Token；用户最终删除和数据地域也未通过。腾讯云上海自托管 Logto 能控制数据地域且没有 Auth 许可证费，但官方最低推荐资源为 `2 vCPU / 8 GiB / 256 GiB`，还需承担 PostgreSQL、SMTP、迁移、备份和持续安全更新，不符合当前低成本、低运维目标。

Authing 仍需通过不接入 Dayfold 业务数据的最小账户验证，确认公有云身份数据地域、免费计划、用户导出、用户删除、回调域名和中国大陆访问表现。只有 Authing 无法满足数据地域要求时，才考虑在腾讯云上海自托管 Logto；自托管会引入额外服务、数据库、升级和安全运维，不符合当前“Simple over Sophisticated”的首选方向。

Supabase Auth、Auth0 和 Clerk 不作为中国大陆正式身份源。它们可以保留为协议兼容性参考，但不得成为正式用户身份或凭据的事实来源。

## 评估标准

所有候选使用同一组标准：

| 维度 | Dayfold 要求 |
|---|---|
| 中国大陆可达性 | 注册、登录、刷新 Token、重置密码在大陆网络可稳定访问 |
| 数据地域 | 能确认正式身份数据的存储和处理地域 |
| 协议 | 支持 OIDC Authorization Code，SPA 场景支持 PKCE |
| 基础能力 | 邮箱注册、邮箱验证、密码重置、会话注销 |
| Token | 提供可验证的 JWT、Issuer、Audience 和公钥发现方式 |
| 用户管理 | 支持查询、禁用、导出和删除身份 |
| 内部映射 | 可将 Provider `sub` 映射到 Dayfold 内部 `user_id` |
| 账户删除 | 能在 Dayfold 数据删除后确定性删除外部身份 |
| Secret 边界 | Client Secret 只存在于 FastAPI 或部署平台 Secret 中 |
| 成本 | 小规模测试可控，定价和升级条件可查 |
| 运维复杂度 | 不要求 Dayfold 自行保存密码哈希或运维身份数据库 |

## 候选比较

| 候选 | 大陆正式方向 | OIDC / JWT | 邮箱密码与重置 | 删除与导出 | 成本可见性 | 运维复杂度 | 结论 |
|---|---|---|---|---|---|---|---|
| Tencent OneID | 地域未确认 | 支持 | 支持 | API 支持删除与导出 | 120000 元/年 + 0.02 元/MAU | 低至中 | P1 / MVP 不采用 |
| Authing 公有云 | 数据地域未知 | 支持 OIDC + PKCE | 支持 | 删除接口存在，免费权限需实测 | 免费版 8,000 MAU | 低 | 仅用于无真实数据技术验证 |
| 自托管 Logto | 地域可完全控制 | 支持 | 支持 | 自行控制 | 软件可免费，基础设施与运维自担 | 高 | 保底 |
| Supabase Auth | 不匹配大陆地域 | 支持 | 支持 | 支持管理接口 | 公开 | 低 | 不采用 |
| 自建 FastAPI Auth | 地域可控 | 自行实现 | 自行实现 | 自行实现 | 表面成本低 | 很高 | 不采用 |

## Tencent OneID

### 已确认能力

Tencent OneID 面向 C 端用户注册、登录和统一账号管理，提供公有云、私有化与混合云部署形态。[腾讯云产品说明](https://cloud.tencent.com/product/ciam)

官方认证接口支持：

- Web、单页应用和移动 App。
- OAuth 2.0 / OIDC 授权码模式。
- Access Token、ID Token 和 Refresh Token。
- JWT 公钥验证。
- 邮箱地址、手机号或用户名作为账号标识。
- 密码设置与重置。

授权码模式允许应用通过回调获得临时 Code，再由可信服务端换取 Token；Dayfold 应采用这一模式，不把 Client Secret 放在 React 前端。[Tencent OneID 授权码模式](https://cloud.tencent.com/document/product/1441/64398)

用户管理 API 提供创建、查询、更新、禁用、批量删除、密码重置、用户导出和审计日志查询。删除和导出接口使账户注销与供应商迁移具备基础能力。[Tencent OneID API 概览](https://cloud.tencent.com/document/product/1441/75534)

### 未确认项

公开文档没有给出足够信息证明公有云身份数据可以固定存储在腾讯云上海地域。产品支持私有化部署，但私有化通常意味着更高成本和运维复杂度。

正式采用前必须确认：

1. 开发者是否可以直接开通公有云，不依赖企业销售流程。
2. 身份目录、审计日志和备份的实际数据地域。
3. 免费额度、按量单价、最低消费和停用规则。
4. 邮件发送服务是否内置，是否需要另购邮件通道。
5. 删除用户后身份数据、日志和备份的保留策略。
6. 用户导出格式是否足以迁移到其他 OIDC Provider。
7. 自定义正式域名的备案和证书要求。

### 最小验证结果

2026-09-21 的账户验证确认：

- 腾讯云账户和 OneID 控制台可以正常访问。
- 未开通状态下只能进入购买流程。
- 高级版购买页显示 120000 元/年。
- 后付费用量显示 0.02 元/MAU，按月结算。
- 购买页没有提供免费试用或地域选择。
- 没有购买、创建实例或产生费用。

因此 Tencent OneID 对 Dayfold P1 / MVP 构成明确成本阻断。完整记录见 `tencent-oneid-minimal-validation-result.md`。

## Authing

### 已确认能力

Authing 支持邮箱、用户名或手机号配合密码登录，并提供邮箱验证、邮箱或手机号重置密码、托管登录页、内嵌组件和 API / SDK。[Authing 账号密码认证](https://docs.authing.cn/v2/guides/authentication/basic/password/)

对于 React/Vite 这类无法安全保存 Client Secret 的浏览器应用，Authing 官方建议使用 OIDC Authorization Code + PKCE。[Authing OIDC PKCE](https://docs.authing.cn/v2/apn/more-oidc-tests/type2.html)

截至 2026-09-21 的公开价格页面显示：

- 免费计划最多 8,000 MAU。
- 基础版为每月 139 元。
- 高级版为每月 1,299 元。
- 私有云需要企业版并单独购买。

价格与功能可能调整，正式采用时必须重新确认。[Authing 价格](https://www.authing.cn/pricing)

### 未确认项

公开安全页面说明了加密、备份和安全认证，但没有明确说明免费或基础公有云用户池的具体存储地域。[Authing 安全与合规](https://www.authing.cn/security)

正式采用前必须确认：

1. 公有云用户池和审计日志的实际数据地域。
2. 免费版能否通过管理 API 完成用户导出和确定性删除。
3. 免费版审计日志只保留一天是否满足故障排查需求。
4. 自定义登录体验和自定义域名是否需要升级。
5. 邮件发送额度、限流和退信处理。
6. 服务停止后的用户和密码凭据迁移能力。

### 免费计划评价

Authing 免费计划提供 8,000 MAU、1 个自建应用、用户管理和最长 1 天审计日志；全部公有云版本共享每用户池 150 QPS。Dayfold 只部署一个正式上线应用，因此应用数量不构成阻断；当前剩余问题是数据地域未知、长期安全审计不足和无 SLA。

Authing 公开说明其核心业务架构在 AWS 上，但没有披露免费用户池的具体数据地域。身份数据包括邮箱、登录历史、IP 和用户标识，在地域未知时不能承载 Dayfold 正式私人数据。完整判断见 `authing-free-plan-evaluation.md`。

## 自托管 Logto

Logto 提供 OIDC、OAuth、密码登录、邮件和短信连接器、用户管理与账户 API。Logto Cloud 免费计划提供用户认证能力，但自定义数据地域只在企业方案中明确提供。[Logto 价格](https://logto.io/pricing)

将 Logto 自托管在腾讯云上海可以控制身份数据地域，但会新增：

- 独立身份服务。
- 独立数据库或额外 Schema。
- 安全更新和版本升级。
- 邮件连接器与密钥管理。
- 备份、监控、可用性和事故响应。

Dayfold 当前仍是单人 P1 项目，这些成本高于其带来的收益。自托管 Logto 只作为托管身份服务不满足数据地域要求时的保底，不进入首版默认架构。

## Supabase Auth

Supabase Auth 能提供邮箱密码、JWT 和用户管理，但 Supabase 当前公开区域列表包括新加坡、东京、首尔等周边区域，没有中国大陆区域。区域同时决定主要项目数据存储位置。[Supabase 可用地域](https://supabase.com/docs/guides/platform/regions)

这与 Dayfold 已冻结的中国大陆正式部署和身份数据地域方向冲突。Supabase Auth 不作为正式身份源，也不因此改变 PostgreSQL 是业务事实来源的架构。

## 自建 Auth

FastAPI 可以自行实现密码哈希、邮箱验证、密码重置、Token、刷新、撤销和风控，但这会把高风险身份安全职责转移给 Dayfold。

自建方案至少需要长期维护：

- 密码哈希参数和升级。
- 邮箱验证与重置 Token。
- 登录限流和防暴力破解。
- Session 撤销与设备管理。
- JWT 密钥轮换。
- 账号枚举防护。
- 审计日志。
- 安全漏洞响应。

这些工作不会直接验证 Dayfold 的 Memory 产品假设，因此首版不自建密码系统。

## 推荐认证架构

推荐协议：

```text
React / Vite
      ↓ redirect
Managed Auth Hosted Login
      ↓ authorization code
FastAPI callback
      ↓ server-side token exchange
OIDC ID Token / Access Token validation
      ↓
Dayfold identity mapping
      ↓
internal user_id
```

关键规则：

- 使用 OIDC Authorization Code；浏览器场景启用 PKCE。
- Client Secret 只保存在 FastAPI 部署环境变量中。
- 不把 Access Token、Refresh Token 或 Client Secret 写入 `localStorage`。
- FastAPI 必须验证 Issuer、Audience、签名、过期时间和 Nonce / State。
- Provider `sub` 只用于身份映射，不直接作为业务表主键。
- 邮箱地址不是稳定主键，也不能作为跨用户查询条件。

Dayfold 内部身份映射最小语义：

```text
internal_user_id
auth_provider
auth_subject
email_snapshot
created_at
updated_at
deleted_at
```

`internal_user_id` 是所有 Journal、Chat、Memory、Growth 和 Retrieval 查询使用的用户边界。更换 Managed Auth 时，业务数据不需要更换主键。

## 账户删除顺序

账户删除必须由 Dayfold 后端协调，不能只删除 Managed Auth 用户：

```text
确认当前用户身份
      ↓
冻结新写入与后台任务
      ↓
删除原始 Journal / Chat
      ↓
失效并删除关联 Memory / Embedding / Retrieval
      ↓
删除 Growth 与用户资料
      ↓
撤销 Session / Refresh Token
      ↓
删除 Managed Auth identity
      ↓
记录不含私人内容的删除结果
```

删除过程必须使用内部 `user_id`，支持幂等重试，并保证跨用户影响为零。若外部身份删除失败，Dayfold 业务数据仍保持不可访问状态，任务进入受控重试，不能恢复用户召回。

## 条件性决策

当前建议调整为：

```text
Authing Free OIDC discovery spike: ACCEPT
Authing Free public real-user MVP: REJECT
Authing Free production identity: REJECT
Self-hosted Logto evaluation: CONDITIONAL / NOT APPROVED
Next validation: Tencent Cloud Shanghai no-purchase price quote
Rejected for P1 / MVP: Tencent OneID
Protocol: OIDC Authorization Code + PKCE
Business identity key: Dayfold internal user_id
```

Authing 只有在最小验证全部通过后才能转为正式采用：

1. 创建独立测试用户目录和 Web 应用。
2. 使用虚构邮箱完成注册、邮箱验证、登录和密码重置。
3. 验证 OIDC discovery、JWKS、Authorization Code 和 PKCE。
4. 验证 FastAPI 可以校验 Issuer、Audience 和签名。
5. 验证用户禁用、导出和删除 API。
6. 确认公有云身份数据和审计日志地域。
7. 获取实际计费规则并设置预算上限。
8. 删除全部测试用户和测试应用。

最小验证只使用虚构账号，不连接 Journal、Chat、Memory、数据库或 Preview 真实访问入口。

## Render PostgreSQL 判断

Render PostgreSQL 在技术上能够运行 Dayfold 所需的 PostgreSQL，并支持 `pgvector` 扩展。[Render PostgreSQL 扩展](https://render.com/docs/postgresql-extensions)

它不适合作为 Dayfold 正式数据库，原因不是 PostgreSQL 功能不足，而是地域边界不匹配。Render 当前公开地域为美国 Oregon、Ohio、Virginia，德国 Frankfurt 和新加坡，没有中国大陆地域；不同地域之间也不能通过 Render 私有网络直接通信。[Render 地域](https://render.com/docs/regions)

因此：

| 用途 | Render PostgreSQL |
|---|---|
| P1 无真实数据实验 | 可以，但当前 Probe 不需要数据库 |
| 虚构数据 Preview | 可以，需独立实例和明确销毁策略 |
| 中国大陆正式数据库 | 不采用 |
| Journal / Chat / Memory | 不允许 |
| 生产 pgvector | 不采用，改用中国大陆同地域 PostgreSQL |

正式数据库继续以腾讯云上海 PostgreSQL + `pgvector` 为首选候选。Render 只保留 FastAPI Preview，不新增数据库。

## P1 状态

Tencent OneID 已因成本阻断退出 P1 / MVP 候选。Authing 免费计划完成账户验证后，仍不满足正式私人数据环境的地域、邮箱流程、JWT 端到端、用户删除和审计要求，因此 P1 继续处于 Closeout。

正式身份方案仍需后续裁决。Logto 评估见 `logto-tencent-shanghai-evaluation.md`。下一项工作只取得上海 CVM、PostgreSQL 与 SES 的长期续费口径报价，不购买或部署资源。

## 明确不实施

本阶段不执行：

- 登录页面开发。
- 数据库 Schema。
- 用户表或 Session 表。
- OAuth 回调代码。
- JWT 中间件。
- 邮件服务接入。
- 真实用户注册。
- Render PostgreSQL 创建。
- Supabase、Auth0 或 Clerk 接入。
- 自托管 Logto 部署。
