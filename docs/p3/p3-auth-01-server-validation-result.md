# P3-Auth-01 CloudBase 服务端验证结果

状态：通过并批准补偿控制，O-02 为 `Decision Frozen / Implementation Ready`
日期：2026-09-22
环境：CloudBase 上海体验环境 `dayfold-p1-probe-d9e0e41d9216f9d`
数据边界：仅使用一次性虚构账号；未接触真实用户、Journal、Chat、Memory 或旧 `trace_memory.db`

## 结论

CloudBase Auth v2 的服务端 AccessToken 验证路径已锁定为：

```text
GET https://{environment_id}.api.tcloudbasegateway.com/auth/v2/user/me
Authorization: Bearer <access_token>
```

有效 Token 返回稳定外部主体 `sub`。FastAPI 适配器应把 `sub` 映射为 `VerifiedIdentity.auth_subject`，再由应用映射为内部 `user_id`；业务代码不得信任前端提交的用户标识，也不得自行接受未验证 JWT 声明。

身份冻结、恢复和删除的行为已通过一次性账号验证。`/auth/v1/user/revoke/all` 已确认为当前用户自助接口，不支持管理员按 UID 调用；MVP 批准“内部状态立即拒绝访问 + 冻结身份 + 删除身份”的补偿控制，因此 O-02 可以提升为 `Implementation Ready`。决策见 `docs/adr/2026-09-22-cloudbase-session-revocation-compensation.md`。

## 验证对象

| 项目 | 值 |
|---|---|
| 虚构用户名 | `dayfold-test1` |
| 虚构用户 UID | `2102321760990294017` |
| 初始状态 | `ACTIVE` |
| 最终状态 | 已删除 |
| 原有账号影响 | `dayfold-p1-test` 与 `administrator` 未修改 |

密码、AccessToken、RefreshToken、验证码和 CAM Secret 均未写入代码、文档、终端输出或对话。

## 实测结果

| 场景 | 观察结果 | 判定 |
|---|---|---|
| 有效登录 | `POST /auth/v2/signin/username` 返回 `200` | 通过 |
| 有效 Token 身份查询 | `GET /auth/v2/user/me?with_datasource=false` 返回 `200` | 通过 |
| 稳定身份 | 返回身份的 `username/sub` 与控制台虚构账号一致 | 通过 |
| Token 基本约束 | JWT 为 RS256，包含 `kid/iss/sub/aud/exp/project_id`；`project_id` 匹配环境，测试时未过期 | 通过 |
| 冻结身份 | 控制台操作由“冻结”切换为“激活”；冻结后登录返回 `400` 和“该用户被停用” | 通过 |
| 冻结后的旧 Token | Token 未过期且 `sub` 未变，但受保护页返回 `INVALID_ACCESS_TOKEN` | 通过 |
| 恢复身份 | 控制台显示“授权成功”；恢复后登录与 `/auth/v2/user/me` 均返回 `200` | 通过 |
| 删除身份 | 控制台显示“删除用户成功”，用户总数由 3 降为 2，目标 UID 不再可查 | 通过 |
| 删除后的旧 Token | Token 未过期且仍指向已删除 UID，但受保护页返回 `INVALID_ACCESS_TOKEN` | 通过 |
| 删除后重新登录 | 登录返回 `400` 和通用“帐号或密码不正确” | 通过 |
| 管理员撤销全部 Session | `/auth/v1/user/revoke/all` 无 UID 参数；TCB 管理 OpenAPI 无对应动作 | 不支持，采用已批准补偿控制 |

旧 Token 被拒绝时，CloudBase 暴露的底层信息是签名密钥无法匹配。Dayfold 不应把该供应商细节透传给客户端，只应返回稳定的 `INVALID_TOKEN`。

## 服务端契约

### Token 验证

```text
verify_access_token(token)
  -> VerifiedIdentity(auth_subject, email)
  -> INVALID_TOKEN
  -> TOKEN_EXPIRED
  -> AUTH_PROVIDER_UNAVAILABLE
```

约束：

- 请求超时为 3 秒。
- `200` 响应必须包含非空字符串 `sub`。
- `email` 可为空。
- `401` 默认映射为 `INVALID_TOKEN`；明确的过期错误映射为 `TOKEN_EXPIRED`。
- 网络错误、`5xx`、不可解析的成功响应或缺失 `sub` 映射为 `AUTH_PROVIDER_UNAVAILABLE`。
- Token 原文不得进入日志、数据库、异常文本或测试快照。

### 身份管理

生产管理面使用腾讯云 TCB OpenAPI：

```text
disable_identity(auth_subject)
  -> ModifyUser(EnvId, Uid, UserStatus=BLOCKED)

enable_identity(auth_subject)
  -> ModifyUser(EnvId, Uid, UserStatus=ACTIVE)

delete_identity(auth_subject)
  -> DeleteUsers(EnvId, Uids=[Uid])
```

控制台内部调用不是生产接口契约。生产实现必须通过服务端 CAM 鉴权或等价工作负载身份调用正式 OpenAPI，且权限仅覆盖目标环境中的用户查询、状态修改和删除。

官方接口：

- `ModifyUser`：https://cloud.tencent.com/document/api/876/127958
- `DeleteUsers`：https://cloud.tencent.com/document/api/876/127960

## Session 撤销边界

`@cloudbase/js-sdk@3.10.0` 中存在用户自助接口：

```text
DELETE /auth/v1/user/revoke/all
```

SDK 类型声明为 `revokeAllDevices(): Promise<void>`，实现使用 `withCredentials: true` 且不接受 UID。它只能让当前用户撤销自己的全部设备，不能供 Dayfold 删除控制面按 `auth_subject` 调用。当前 TCB 管理 OpenAPI 概览也没有对应的 Session 撤销动作。

因此：

- 用户主动“退出全部设备”可以作为客户端辅助动作单独验证。
- `revoke_sessions(auth_subject)` 不进入 MVP 管理适配器。
- 注销事务先把内部用户设为 `deletion_pending`；FastAPI 从事务提交起拒绝该用户所有业务请求。
- 删除控制面随后执行 `ModifyUser(BLOCKED)`、状态确认、业务数据清理和 `DeleteUsers`。
- 该方案承诺“立即失去 Dayfold 访问权”，不宣称供应商中的所有 Session 对象均被显式撤销。

## 代码证据

当前最小实现：

- `apps/api/auth/cloudbase.py`
- `apps/api/tests/test_cloudbase_auth.py`

单元测试覆盖：

- Bearer Header 与真实 `/auth/v2/user/me` 路径。
- 有效响应映射到稳定 `auth_subject`。
- 无效、过期和供应商不可用错误映射。
- 非 JSON `5xx` 与缺失 `sub` 不泄漏底层解析异常。

该实现尚未接入 `apps/api/main.py`，没有新增业务路由、用户表或生产凭据。

## 权限与审计

| 主体 | 最小权限 | Secret 位置 | 必须审计 |
|---|---|---|---|
| Web 用户 | 登录、刷新、读取自身身份 | CloudBase SDK 管理，不进入服务端日志 | 登录成功/失败、退出 |
| FastAPI 验证路径 | 调用 `/auth/v2/user/me` | 仅接收请求中的短期 Bearer Token | 验证结果、错误码、耗时；不记 Token |
| 删除控制面 | 指定环境内查询、冻结、恢复、删除用户 | 部署平台 Secret 或工作负载身份 | 操作者、目标 UID、动作、结果、请求 ID |
| 人工管理员 | Preview 环境的受控用户管理 | 腾讯云控制台会话 | 冻结、恢复、删除 |

## 后续验证

1. 管理端 CAM 最小权限策略尚未在独立服务身份上验证。
2. Staging 需验证注销事务提交后，同一 Token、另一设备 Token 和 RefreshToken 均无法访问 Dayfold。
3. 真实 FastAPI 进程尚未使用浏览器会话 Token 执行端到端调用；本次在线证据来自 CloudBase 登录页对同一 `/auth/v2/user/me` 的实际 `200` 请求，服务端适配器通过契约测试验证。

## 下一步

1. 实现内部用户 `deletion_pending` 状态门禁和独立删除控制面。
2. 在 Staging 创建最小权限服务身份，验证 `ModifyUser`、`DescribeUserList`、`DeleteUsers` 和审计日志。
3. 使用安全注入的短期测试 Token 运行 FastAPI 多设备和 RefreshToken 集成测试，不把 Token 写入命令历史、文件或测试报告。
4. Staging 验收通过后，将账户删除能力标记为 `Production Validated`。
