# CloudBase HTTP 用户状态门禁设计

状态：Approved for implementation  
日期：2026-09-23

## 目标

在 CloudBase 个人版共享 PostgreSQL 不提供网络连接地址的条件下，让 FastAPI
继续执行内部用户状态门禁。仅 `active` 且未删除的用户可以访问受保护接口；
其他状态和缺失映射统一拒绝，状态服务异常时安全关闭。

## 决策

新增 `CloudBaseHttpUserStatusStore`，通过 CloudBase PostgreSQL HTTP API 查询
`public.users`。适配器转发当前请求已经通过 `/auth/v2/user/me` 验证的用户
AccessToken，不引入管理员 API Key。

保留 `PostgresUserStatusStore`。部署通过 `DAYFOLD_USER_STATUS_BACKEND` 显式选择
`cloudbase_http` 或 `postgres`；未识别或缺少必要配置时不创建状态存储，门禁返回
`503 USER_STATUS_UNAVAILABLE`。

## 调用链

1. FastAPI 解析 Bearer Token。
2. `CloudBaseAuthAdapter` 验证 Token 并取得 `auth_subject`。
3. 状态存储接收 `auth_subject` 和原始 AccessToken。
4. HTTP 适配器查询：
   `users?select=status&auth_subject=eq.<subject>&deleted_at=is.null&limit=1`。
5. 仅返回唯一且合法的状态值；空数组表示缺失映射。
6. 门禁仅允许 `active`，其余结果统一返回 `401 INVALID_TOKEN`。

## RLS

`public.users` 保持启用 RLS。新增仅限 `authenticated` 的 SELECT Policy：

```sql
USING (
  auth_subject = (SELECT auth.uid())::text
  AND deleted_at IS NULL
)
```

不向 `anon` 授权，不创建 INSERT、UPDATE 或 DELETE Policy。查询参数用于缩小结果集，
RLS 是最终授权边界。

## 错误语义

- HTTP `200` 且空数组：缺失映射，返回 `None`。
- HTTP `200` 且唯一合法状态：返回该状态。
- HTTP `401/403`：Token 在数据库 API 层被拒绝，返回 `None`，门禁输出通用 `401`。
- 超时、网络错误、`5xx`、其他状态码、异常 JSON、多行结果或异常字段：抛出
  `UserStatusStoreUnavailable`，门禁返回通用 `503`。
- 错误信息不得包含 Token、响应正文或供应商内部细节。

## 测试

- HTTP 请求使用 Bearer Token、绑定查询参数并限制返回字段。
- 覆盖 `active`、缺失映射、`401/403`、`5xx`、网络失败、异常 JSON 和多行结果。
- 覆盖后端选择与缺少配置的安全关闭。
- 确认 FastAPI 将原始 Token 传给状态存储。
- 保留 PostgreSQL 参数绑定测试。

## 非目标

- 不实现用户状态写入、注销控制面或业务表访问。
- 不使用管理员 API Key。
- 不删除 PostgreSQL 直连适配器。
- 不部署 Production Schema。
