# P3-Auth-02 状态门禁与会话验证进度

状态：HTTP 状态门禁与 RLS 已部署，单设备最小生命周期验收通过  
日期：2026-09-23  
数据边界：仅使用虚构身份；本文不含密码、Token、Cookie、数据库连接串或 CAM Secret

## Baseline 证据

此前实际运行已确认：

- 两个独立设备的旧 AccessToken 均可访问 CloudBase 身份接口和 Dayfold 探针。
- 两个设备映射到同一 `sub`。
- RefreshToken 契约为 `latest_session_only`：最后登录设备可换发，较早设备返回 `404`。
- 换发得到的新 AccessToken 可访问 CloudBase 身份接口和当时版本的 Dayfold 探针。

该次运行未通过 `--output` 保留脱敏 JSON，临时凭据随后已安全删除。因此以上内容是已验证结论的脱敏摘要，不替代可复现的 Staging 验收产物；本轮没有伪造或重建原始输出。

## 单设备最小生命周期

2026-09-23 使用同一设备的旧 AccessToken 完成 Staging 在线验证：

- `active`：CloudBase 身份接口返回 `200`，Dayfold 探针返回 `200`。
- `deletion_pending`：CloudBase 身份接口仍返回 `200`，Dayfold 探针立即返回通用 `401 INVALID_TOKEN`。
- 恢复 `active`：CloudBase 身份接口和 Dayfold 探针均恢复为 `200`。
- 验证期间未冻结或删除 CloudBase 身份，未删除用户映射。
- 脱敏机器可读证据保存于 `docs/p3/p3-auth-02-single-device-lifecycle.json`，不含 Token、Cookie 或密码。

该结果确认内部状态门禁可以在 AccessToken 仍被 CloudBase 接受时立即拒绝访问。双设备 blocked/deleted 完整生命周期仍作为后续正式开放账号注销前的验证缺口。

## 状态门禁

当前实现按以下顺序处理 `/v1/auth/probe`：

1. 通过 CloudBase 验证 AccessToken 并取得 `auth_subject`。
2. 使用绑定参数查询未删除的内部 `users` 映射。
3. 仅 `active` 返回 `200`。
4. `deletion_pending`、`disabled`、未知状态、缺失映射和已删除映射统一返回 `401 INVALID_TOKEN`。
5. `DATABASE_URL` 未配置或数据库查询失败时返回 `503 USER_STATUS_UNAVAILABLE`，不绕过门禁。

未创建 Production Schema，未实现 Journal、Chat、Memory 或删除控制面。

## Preview Schema

已在 `dayfold-p1-probe` 体验环境的 `public` Schema 创建最小 `users` 表：

- 字段：`id`、`created_at`、`auth_subject`、`status`、`deleted_at`。
- `auth_subject` 为非空唯一值。
- `status` 为非空值，只允许 `active`、`deletion_pending`、`disabled`。
- 已创建未删除用户的 `auth_subject` 部分索引。
- 已启用 RLS。
- 已撤销 `anon` 和 `authenticated` 的原有表级权限。
- `authenticated` 仅可选择 `auth_subject`、`status`、`deleted_at`。
- `users_select_self` Policy 仅允许用户读取 `auth.uid()` 对应且未删除的自身映射。
- 已写入 1 条 `active` 虚构用户映射；验证查询只返回状态和数量。

数据库仍为空闲 Preview 验证资源，不是 Production Schema。

## CloudBase 个人版

环境已升级为 CloudBase 个人版。升级后 PostgreSQL 仍为共享集群：

- 内网地址为空。
- 外网 IPv4 开启按钮不可用。
- 数据库密码不可查看，只能重置；重置会断开现有连接。
- 当前没有用户自建数据库角色。

因此共享集群不使用 `DATABASE_URL`。新增
`CloudBaseHttpUserStatusStore`，把已验证的当前用户 AccessToken 转发到 PostgreSQL
HTTP API，并由数据库 RLS 执行自身行授权。该路径不使用数据库密码或管理员 API Key。

HTTP 适配器遵循以下错误语义：

- `200` 且唯一合法状态：返回内部状态。
- `200` 且空数组、`401` 或 `403`：按缺失或不可访问映射处理，门禁返回通用 `401`。
- 网络错误、超时、`5xx`、其他状态码、异常 JSON、多行或非法状态：
  返回 `503 USER_STATUS_UNAVAILABLE`。
- 所有错误均不记录或回传 Token、响应正文或供应商内部信息。

RLS 已通过控制台执行并查询 `pg_policies` 验证：

```text
policyname: users_select_self
roles: authenticated
cmd: SELECT
qual: auth_subject = auth.uid() AND deleted_at IS NULL
```

本地迁移文件：

```text
infra/cloudbase/migrations/20260923_users_select_self.sql
```

## 本地验证

```text
python3 -m pytest apps/api/tests -q
58 passed

python3 -m compileall -q apps/api
passed

psycopg
3.3.6
```

测试覆盖 `active`、`deletion_pending`、`disabled`、缺失映射、Token 转发、HTTP
权限拒绝、异常响应、状态存储不可用、绑定参数查询和数据库错误归一化。

## 待完成验收

1. 在正式开放账号注销前，重新建立两个可复现的独立设备会话。
2. 保存新的脱敏双设备 `baseline` JSON。
3. 验证两个旧 AccessToken 和可换发的新 AccessToken 在 `deletion_pending` 后均被 Dayfold 拒绝。
4. 完成 CloudBase `BLOCKED` 和 `DELETE` 后分别运行 `blocked`、`deleted`，保存脱敏结果。
