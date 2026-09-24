# Authing 免费计划对 Dayfold P2 MVP 的适用性评估

状态：账户验证部分通过，不批准正式上线  
日期：2026-09-21  
当前阶段：P1 Closeout  
适用范围：Authing 免费计划、P2 认证技术验证与正式私人数据边界

## 结论

Authing 免费计划可以支持 OIDC Discovery 与 JWKS 基础验证，但邮箱流程、JWT 端到端、用户最终删除和数据地域未通过，因此不足以作为接收真实 Journal、Chat、Memory 和 Growth 数据的正式 P2 MVP 身份方案。

这里需要区分两个目标：

| 目标 | Authing 免费计划 |
|---|---|
| 无真实数据的认证技术验证 | 足够 |
| 仅开发者使用的本地或受控测试 | 条件性足够 |
| 公开注册的 P2 MVP | 不足 |
| 承载真实私人数据的正式环境 | 不采用 |

免费计划可以验证邮箱注册、邮箱验证、密码重置、OIDC Authorization Code + PKCE、JWT 和 Dayfold 内部 `user_id` 映射。Dayfold 决定只部署一个正式上线应用，因此一个自建应用的额度足够；剩余问题是正式身份数据地域、长期审计、SLA 和自定义正式域名。

## P2 最小需求

Dayfold 的身份能力不是独立功能展示，而是私人数据隔离的前置条件。P2 MVP 至少需要：

- 邮箱注册和邮箱验证。
- 密码登录与密码重置。
- OIDC Authorization Code + PKCE。
- 可验证的 JWT、Issuer、Audience 和公钥。
- Provider `sub` 到内部 `user_id` 的稳定映射。
- 用户禁用和删除。
- 一个正式 Authing 应用及严格的回调地址白名单。
- 足够的登录与管理员操作审计。
- 明确的身份数据存储地域。
- 可预期的价格和退出路径。

其中前五项可以先用虚构账号验证，后五项决定是否能接收真实私人数据。

## 免费计划能力

### 容量与应用

Authing 公开价格页显示，免费计划包括：

- 最多 8,000 MAU。
- 1 个自建应用。
- 1 个社会化账号连接。
- 用户管理。
- 短信验证码共计 10 条。
- 审计日志最长保留 1 天。
- 不提供 SLA。
- 不提供自定义域名、自定义用户协议、Webhooks 和自定义工作流。[cite:1]

8,000 MAU 对 Dayfold P2 技术验证足够。容量不是当前阻断项。

1 个自建应用符合 Dayfold 当前只部署正式上线版本的决定，不再构成免费计划阻断。该应用只能配置正式域名和必要的本地开发回调地址，不配置独立 Preview 回调，也不与其他项目共享 Client、Secret 或用户目录。

### 邮箱密码流程

Authing 文档说明账号密码认证支持邮箱、用户名和手机号，并提供邮箱验证、邮箱或手机号重置密码、托管登录页、内嵌组件和 API / SDK。[cite:2]

这些能力覆盖 Dayfold P2 认证技术验证所需的注册、登录、邮箱验证和密码重置。实际邮件额度、发送延迟、退信处理和免费计划限制仍需在测试用户池中验证。

### OIDC 与 PKCE

Authing 官方建议 SPA 和移动应用使用 OIDC Authorization Code + PKCE，并公开 `/.well-known/openid-configuration`、授权端点、Token 端点和 UserInfo 流程。[cite:3]

这一协议与 React/Vite + FastAPI 方向兼容。技术验证可以检查：

```text
React / Vite
      ↓ Authorization Code + PKCE
Authing
      ↓ ID Token / Access Token
FastAPI
      ↓ validate issuer / audience / signature
Dayfold internal user_id
```

免费计划是否对具体 OIDC 配置施加额外限制，仍需账户验证。

### API 容量

Authing 公开 API 文档说明，当前公有云全部版本的请求上限为每用户池每秒 150 次，超出后返回 `429`，三秒后解除限制。[cite:4]

150 QPS 明显高于个人项目 P2 MVP 的预期认证负载。API 限流不是当前阻断项，但 FastAPI 仍需要处理 `429`、超时和 Authing 业务状态码，不能只根据 HTTP `200` 判断成功。

### 用户查询和删除

管理 API 提供用户查询、用户列表和批量删除接口。批量删除接口为 `/api/v3/delete-users-batch`，通过用户 ID 列表删除身份。[cite:5][cite:6]

公开文档证明接口存在，但没有证明免费计划实际允许调用。Authing 对需要升级的接口可能返回 `402 PaymentNeededError`，因此免费计划的用户删除能力必须用虚构账号实测。

用户列表接口每页最多返回 50 条，可作为小规模测试用户导出的基础。[cite:4][cite:6] 正式迁移还需要验证密码凭据能否导出；通常身份服务不会导出可直接迁移的密码明文或哈希，不能把“能导出用户资料”理解成“能无感迁移全部账号”。

## 数据地域

Authing 安全页面说明其数据使用 AES-256 加密、SSL/TLS 传输、KMS 密钥轮换、多副本和备份，但没有公布免费公有云用户池的具体存储地域。[cite:7]

Authing 的云原生介绍明确写明其核心业务架构在 AWS 上，但同样没有说明免费用户池对应的 AWS 区域，也没有提供用户自选地域的公开配置。[cite:8]

因此数据地域状态为：

```text
UNKNOWN
```

Dayfold 已冻结中国大陆正式部署方向。身份数据包括邮箱、登录记录、IP 和用户标识，也属于私人数据。未确认地域前，Authing 免费计划不能成为正式身份源。

## 安全与运维限制

### 审计日志

免费计划的审计日志最长保留 1 天。[cite:1] 这不足以调查跨日出现的异常登录、删除失败或账号接管问题。

P2 认证技术验证可以接受一天日志，因为测试周期短且不接收真实数据。正式 MVP 需要更长的日志保留，或将不含私人内容的必要安全事件同步到 Dayfold 自有日志系统；免费计划不提供 Webhooks，因此后者也不能直接依赖事件推送。

### SLA

免费计划没有 SLA 和客服响应承诺。[cite:1] 对内部技术验证可接受，对承载长期个人记录的正式服务不合适。

### 域名与品牌

免费计划不提供自定义域名，也不提供自定义用户协议和完整品牌化。[cite:1] 登录流程将依赖 Authing 二级域名。

这不会阻止 OIDC 技术验证，但会破坏 Dayfold 正式入口的一致性。更重要的是，正式注册流程需要展示 Dayfold 自己的隐私说明和用户协议，不能只依赖身份供应商页面。

## 预算判断

用户明确拒绝每月 139 元的基础版固定成本。因此评估边界是：

```text
Auth license recurring cost = 0 元
```

免费计划本身满足这一边界，且一个自建应用符合当前单一正式版本策略。不能通过后续升级基础版来补齐日志和支持；任何设计只要依赖基础版功能，就不属于当前可接受方案。

邮件、短信、域名和云资源仍可能产生独立费用。P2 技术验证应只使用虚构邮箱和极少量测试账号，不启用短信。

## 适用范围

### 允许

- 创建一个隔离的 Authing 免费用户池。
- 创建一个测试应用。
- 使用虚构邮箱注册。
- 验证邮箱验证和密码重置。
- 验证 OIDC Discovery、JWKS 和 PKCE。
- 验证 FastAPI 对测试 JWT 的签名、Issuer 和 Audience。
- 验证 Provider `sub` 到内部测试 `user_id` 的映射。
- 验证用户查询、禁用和删除。
- 测试结束后删除应用、用户池和虚构账号。

### 禁止

- 保存真实 Journal、Chat、Memory 或 Growth。
- 接收公开用户注册。
- 把 Authing 用户 ID 直接作为业务表主键。
- 在前端保存 User Pool Secret 或 App Secret。
- 添加未经批准的 Preview、测试或第三方回调地址。
- 把免费计划的 8,000 MAU 理解为生产可用性承诺。
- 在数据地域未知时把 Authing 写成正式身份源。

## 决策建议

当前建议为：

```text
Authing Free:
  technical auth spike = ACCEPT
  public real-user MVP = REJECT
  production private-data identity = REJECT
```

P1 不应因为 Authing 免费计划具备基本登录功能而提前进入公开 P2 产品开发。

如果目标是尽快学习并验证 OIDC，可以创建免费测试用户池完成一次虚构账号闭环。如果目标是让真实用户长期保存日记与 Memory，则需要继续评估数据地域可控且无固定 Auth 许可费的方案。

## 下一步

2026-09-21 的免费账户验证结果为：

1. 免费用户池和示例应用可用，不需要付款方式。
2. OIDC Discovery、PKCE 配置和 RS256 JWKS 通过。
3. 数据地域没有可选项，保持 `UNKNOWN`。
4. 免费邮件需要实名认证，虚构邮箱流程没有完成。
5. 用户禁用与恢复通过。
6. 删除入口存在，但最终删除未完成。
7. 未获得 ID Token，JWT 端到端未验证。

完整记录见 `authing-free-account-validation-result.md`。Authing 免费计划只保留为无真实数据的 OIDC 学习环境，不进入正式身份架构。

## Sources

[cite:1] Authing 价格与功能比较：https://www.authing.cn/pricing

[cite:2] Authing 账号密码认证：https://docs.authing.cn/v2/guides/authentication/basic/password/

[cite:3] Authing OIDC Authorization Code + PKCE：https://docs.authing.cn/v2/apn/more-oidc-tests/type2.html

[cite:4] Authing API Explorer 开发准备与接口限流：https://api-explorer.authing.cn/?tag=group/%E5%BC%80%E5%8F%91%E5%87%86%E5%A4%87

[cite:5] Authing 批量删除用户：https://api-explorer.authing.cn/?tag=tag/%E7%AE%A1%E7%90%86%E7%94%A8%E6%88%B7/API%20%E5%88%97%E8%A1%A8/operation/UsersManagementController_deleteUsersBatch

[cite:6] Authing 获取和搜索用户列表：https://api-explorer.authing.cn/?tag=tag/%E7%AE%A1%E7%90%86%E7%94%A8%E6%88%B7/API%20%E5%88%97%E8%A1%A8/operation/UsersManagementController_listUsers

[cite:7] Authing 安全与合规：https://www.authing.cn/security

[cite:8] Authing 云原生基础设施：https://www.authing.cn/cloud-native
