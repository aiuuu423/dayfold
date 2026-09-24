# Authing 免费账户验证结果

状态：部分通过，不批准正式上线  
日期：2026-09-21  
当前阶段：P1 Closeout  
数据范围：Authing 免费用户池、示例应用和虚构测试条目

## 结论

Authing 免费计划可以支持 OIDC/JWKS 基础技术验证，但不能作为 Dayfold 正式私人数据身份源。

账户级验证确认免费用户池和一个示例应用可以使用，OIDC Discovery 和 JWKS 端点正常；邮箱验证码流程因免费邮件实名认证前置条件未完成，未获得实际 ID Token。数据地域仍不可确认，用户删除界面存在但未完成最终删除。

本次没有付费，没有创建真实身份，也没有连接 Journal、Chat、Memory、Growth 或生产数据库。

## 验证结果

| 验证项 | 结果 | 说明 |
|---|---|---|
| 免费用户池 | 通过 | 登录控制台后已存在免费用户池 |
| 免费额度 | 通过 | 控制台显示 8,000 MAU 和免费短信额度 |
| 付款方式 | 通过 | 使用免费用户池不需要绑定付款方式 |
| 自建应用 | 通过 | 免费用户池自动包含一个示例 Web 应用 |
| 第二个应用 | 不支持 | 一个自建应用额度已被示例应用占用，新增应用要求升级 |
| 数据地域 | 未通过 | 控制台没有地域选择或地域说明 |
| 邮箱验证码 | 未通过 | 免费邮件额度要求先完成实名认证或企业认证 |
| 邮箱用户创建 | 未完成 | 用户列表没有新增邮箱用户 |
| OIDC Discovery | 通过 | 服务发现端点可访问 |
| Authorization Code | 配置通过 | Discovery 声明支持 `authorization_code` |
| PKCE | 配置通过 | Discovery 声明支持 `plain` 和 `S256` |
| Refresh Token | 配置通过 | Discovery 声明支持 `refresh_token` |
| JWKS | 通过 | JWKS 返回 RS256 公钥和 `kid` |
| ID Token | 未验证 | 邮箱登录未完成，未获得真实测试 Token |
| JWT 签名验证 | 未验证 | 没有 ID Token 可供验证 |
| 用户列表 | 通过 | 控制台可查看虚构用户条目 |
| 用户禁用 | 通过 | 虚构 `test` 条目成功禁用 |
| 用户恢复 | 通过 | 禁用后已恢复为正常状态 |
| 用户删除入口 | 通过 | 控制台提供删除账号和确认流程 |
| 用户最终删除 | 未完成 | 删除动作未成功执行，不能标记为通过 |
| 实际费用 | 0 元 | 没有升级或购买 |

## 数据地域

免费用户池的基础设置、费用管理和应用设置中没有地域字段，也没有数据中心选择。

Authing 公共资料说明核心业务架构位于 AWS，但没有说明当前免费用户池对应的 AWS 区域。控制台也没有提供可验证的中国大陆地域信息。

状态保持：

```text
UNKNOWN
```

身份数据包含邮箱、手机号、IP、登录历史和外部身份标识。Dayfold 已冻结中国大陆正式部署方向，因此地域未知直接阻断真实私人数据上线。

## 邮箱流程

控制台显示：

```text
Authing 公有云免费用户池每天 50 次邮件额度
需要完成实名认证或企业认证后方可使用
```

托管登录页提供邮箱或手机号验证码登录并自动注册。使用虚构邮箱的尝试没有完成，用户列表中没有新增邮箱用户。

由于没有保存失败页面的具体错误提示，不能把失败根因完全归因于实名认证；但实名认证是控制台明确列出的免费邮件前置条件。在不提交真实身份认证材料的前提下，邮箱注册、邮箱验证和密码重置无法继续验证。

## OIDC 与 JWT

示例应用的 OIDC Discovery 端点正常返回：

- `issuer`
- `authorization_endpoint`
- `token_endpoint`
- `userinfo_endpoint`
- `jwks_uri`
- `authorization_code`
- `refresh_token`
- PKCE `S256`

JWKS 端点返回：

```text
kty = RSA
alg = RS256
use = sig
kid = present
```

这些结果证明 Authing 免费应用具备标准 OIDC 和 JWT 公钥发现能力。

邮箱登录没有完成，因此没有获得真实测试 ID Token，以下内容仍未验证：

- Token 的 `iss` 与 Discovery 是否一致。
- Token 的 `aud` 是否等于应用 Client ID。
- RS256 签名验证。
- `exp`、`iat`、`nonce` 和 `sub`。
- `sub` 到 Dayfold 内部 `user_id` 的实际映射。
- Refresh Token 撤销。

配置能力通过不等于 JWT 端到端通过。

## 用户状态与删除

控制台允许查看虚构用户，并提供：

- 禁用账号。
- 启用账号。
- 删除账号。
- 强制下线。
- 重置密码。
- 发送重置密码链接。

虚构 `test` 条目成功禁用，随后恢复为正常状态。这证明免费用户池具备基础用户状态管理权限。

删除账号入口和确认流程可见，但最终删除没有成功执行，因此只能证明 UI 和产品能力存在，不能证明免费计划的删除请求已经完成。

本次没有修改另一个含手机号的条目，也没有删除用户池或示例应用。

## 安全与隐私

本次验证：

- 没有记录测试邮箱、手机号或验证码。
- 没有复制 App Secret、用户池 Secret 或 Access Token。
- 没有创建 Dayfold 数据库用户。
- 没有连接任何真实日记或聊天。
- 没有付费升级。
- 临时禁用的虚构账号已恢复。
- 没有删除现有用户池和应用。

## 决策

Authing 免费计划的最终判断：

```text
Free user pool: PASS
OIDC Discovery: PASS
JWKS: PASS
Email flow: BLOCKED
JWT end-to-end: NOT VERIFIED
User state management: PASS
User deletion: NOT VERIFIED
Data region: UNKNOWN
Production approval: REJECT
```

它可以保留为无真实数据的 OIDC 学习环境，不进入 Dayfold 正式身份架构。

## 下一步

零固定 Auth 许可费和中国大陆数据地域同时成立时，下一项候选只能转向：

```text
腾讯云上海自托管 Logto
```

下一任务只评估部署成本、最小资源、PostgreSQL 复用、安全更新和单人运维负担，不立即部署。
