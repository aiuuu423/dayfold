# ADR：CloudBase Session 撤销补偿控制

状态：Accepted for MVP Implementation
日期：2026-09-22
影响范围：身份认证、账户注销、租户访问门禁

## 决策

Dayfold 不把 `/auth/v1/user/revoke/all` 作为管理员按 UID 撤销 Session 的接口。MVP 采用“应用内立即拒绝访问 + CloudBase 冻结身份 + 删除身份”的补偿控制，并将 O-02 提升为 `Decision Frozen / Implementation Ready`。

该决策只代表接口和状态足以进入实现，不代表生产验证完成。Staging 必须证明旧 AccessToken、RefreshToken 和多设备会话均无法访问 Dayfold 私人数据，才能进入 Production Provisioning Gate。

## 证据

### SDK 调用语义

`@cloudbase/js-sdk@3.10.0` 的类型和实现均显示：

```text
revokeAllDevices(): Promise<void>
DELETE /auth/v1/user/revoke/all
withCredentials: true
```

方法没有 UID 参数，并携带当前会话凭据。因此它是“当前用户撤销自己的全部设备”，不是管理员选择任意 UID 的管理接口。

### 管理 API 范围

腾讯云 TCB API 概览的用户管理动作包括 `CreateUser`、`DescribeUserList`、`ModifyUser` 和 `DeleteUsers`，未列出按 UID 撤销 Session 的动作。

正式管理接口已经明确支持：

- `ModifyUser(EnvId, Uid, UserStatus=BLOCKED|ACTIVE)`
- `DeleteUsers(EnvId, Uids)`

官方资料：

- TCB API 概览：https://cloud.tencent.com/document/api/876/34809
- `ModifyUser`：https://cloud.tencent.com/document/api/876/127958
- `DeleteUsers`：https://cloud.tencent.com/document/api/876/127960
- AccessToken 生命周期：https://docs.cloudbase.net/http-api/basic/access-token

### P3-Auth-01 实测

一次性虚构账号验证表明：

- `BLOCKED` 后，新登录返回“该用户被停用”。
- `BLOCKED` 后，冻结前签发且尚未过期的 AccessToken 被拒绝。
- 恢复 `ACTIVE` 后可以重新登录。
- `DeleteUsers` 完成后，用户不可查询、不可登录，删除前的未过期 AccessToken 被拒绝。

## 删除顺序

账户注销使用以下顺序：

```text
active
  -> access_denied
  -> identity_blocked
  -> data_purged
  -> identity_deleted
  -> completed
```

1. 接受注销请求的数据库事务把内部用户状态改为 `deletion_pending`，并创建独立删除控制记录和回执。
2. 从事务提交开始，所有 FastAPI 业务请求必须同时验证 CloudBase 身份与内部用户状态；非 `active` 用户统一返回 `401 INVALID_TOKEN`。
3. Web 客户端清除本地凭据并调用当前用户登出。该动作是用户体验和设备清理措施，不是安全门禁，也不阻塞服务端删除。
4. 删除控制面调用 `ModifyUser(UserStatus=BLOCKED)`，并通过 `DescribeUserList` 或等价正式查询确认状态为 `BLOCKED`。
5. 只有内部访问已拒绝且身份已冻结后，才能清理 Dayfold 业务数据。
6. 清理完成后调用 `DeleteUsers`，并确认目标 UID 不再可查询。
7. 删除回执进入 `completed`；控制记录和审计记录按既定保留期保存。

## 安全边界

补偿控制成立必须同时满足：

- Dayfold 私人数据只通过 FastAPI 访问。
- CloudBase 的 `anon` 和 `authenticated` 角色不能直接读取或写入 Dayfold 私人业务表、对象存储或管理接口。
- FastAPI 每次请求都查询内部用户状态，不允许只验证 JWT 后直接进入业务模块。
- `deletion_pending`、`disabled`、缺失用户映射和已删除用户均 fail closed。
- 删除控制面使用独立服务身份；CAM/API Key 只存于部署平台 Secret，不能进入前端、Git、日志或删除记录。
- 冻结、恢复、删除必须记录操作者、目标 UID、请求 ID、结果和时间，不记录 Token。

如果未来开放前端直连 CloudBase 数据库或存储，本 ADR 自动失效，必须先获得正式 Session 撤销能力或新增等价的资源级拒绝策略。

## 失败处理

| 阶段 | 失败行为 |
|---|---|
| 内部状态切换失败 | 不接受注销请求，不开始后续删除 |
| CloudBase 冻结失败 | 保持 `deletion_pending`，Dayfold 继续拒绝访问，后台重试并告警 |
| 数据清理失败 | 身份保持冻结，按退避策略持续重试 |
| CloudBase 删除失败 | 业务数据保持已清理状态，身份保持冻结，持续重试 |
| 状态确认超时 | 不推进下一阶段，记录请求 ID 并告警 |

不得因为 CloudBase 管理接口暂时不可用而把内部用户恢复为 `active`。

## Staging 验收

使用仅含合成数据的虚构账号验证：

1. 注销请求提交后，同一 AccessToken 的后续 FastAPI 请求立即返回 `401 INVALID_TOKEN`。
2. 另一设备已有 AccessToken 也无法访问 Dayfold。
3. RefreshToken 不能重新获得可访问 Dayfold 的会话；即使供应商仍签发 Token，内部状态门禁仍拒绝。
4. `BLOCKED` 状态确认后才开始业务数据清理。
5. 删除完成后 UID 不可查询，旧 Token 和密码登录均失败。
6. 任一步骤重试不会重复删除其他用户，也不会让账号恢复访问。
7. 审计记录不包含密码、AccessToken、RefreshToken、Cookie 或私人内容。

## 替代方案

### 使用 `/auth/v1/user/revoke/all`

拒绝。该接口属于当前用户会话语义，没有 UID 参数，且 v1 登录认证已停止更新，不能作为服务端删除控制面的生产契约。

### 等待腾讯云新增管理接口

不作为 P3 实现前置条件。若腾讯云后续提供正式按 UID 撤销接口，应新增 ADR，将它插入 `access_denied` 与 `identity_blocked` 之间，并保留内部状态门禁作为纵深防御。

### 仅调用 `DeleteUsers`

拒绝。删除前缺少立即生效的应用内门禁和可重试冻结阶段，无法安全处理业务数据清理失败或供应商暂时不可用。

## 结果

`revoke_sessions(auth_subject)` 从 MVP 必需管理适配器中移除。账户删除的安全承诺改为“从注销事务提交起立即失去 Dayfold 访问权”，而不是“供应商中的所有 Session 对象均已显式撤销”。

O-02 可进入实现；进入生产前仍需通过本 ADR 的 Staging 验收，并验证最小权限服务身份和审计日志。
