# Dayfold API Preview

这是 P1 Minimal Deployment Probe 的最小 FastAPI 服务。它只提供 `GET /health`，用于验证静态 Preview、HTTPS 和 CORS 链路，不属于 P2 产品后端。

## 本地运行

在仓库根目录安装依赖：

```bash
python3 -m pip install --break-system-packages -r apps/api/requirements.txt
```

启动 API：

```bash
python3 -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8001
```

另开一个终端启动静态页面：

```bash
python3 -m http.server 8000 --directory apps/web
```

打开 `http://localhost:8000`，在页面中输入 `http://127.0.0.1:8001`。

## CORS 白名单

默认只允许本地静态服务器：

```text
http://localhost:8000
http://127.0.0.1:8000
```

Preview 部署必须通过环境变量显式传入完整 Origin，多个值用逗号分隔：

```bash
export DAYFOLD_ALLOWED_ORIGINS="https://your-preview.example"
```

配置不接受 `*`，也不启用跨域凭据。

## 自动测试

```bash
python3 -m pytest apps/api/tests -v
```

## PythonAnywhere Preview

PythonAnywhere 的 ASGI 支持仍是 beta，本配置只用于 P1 公网连通性验证，不代表 Dayfold 的生产部署平台已经冻结。

示例进程命令：

```text
$HOME/.virtualenvs/dayfold-probe/bin/uvicorn --app-dir $HOME/dayfold/apps/api --uds ${DOMAIN_SOCKET} main:app
```

部署时需要：

1. 在平台环境中设置 `DAYFOLD_ALLOWED_ORIGINS` 为实际 Vercel HTTPS Origin。
2. 使用平台当前文档提供的 ASGI 建站命令绑定上述进程。
3. 分别验证直接访问 `/health` 与 Vercel 页面跨域请求。

API Key、平台 Token、真实日记、私人对话和任何用户数据都不得写入仓库、页面或测试结果。

## Staging Auth 会话验证

`apps.api.scripts.staging_auth_sessions` 用于验证账户注销补偿控制下的两设备 AccessToken 和 RefreshToken 行为。脚本不创建、冻结或删除账号，只读取环境变量中的两组虚构会话凭据，并输出不含凭据的 JSON 结果。

运行前，Staging API 必须提供一个只读受保护探针：

```text
GET /v1/auth/probe
active 用户 -> 200
deletion_pending、disabled、缺失映射或已删除用户 -> 401 或 403
```

需要设置：

```text
DAYFOLD_CLOUDBASE_ENV_ID
DAYFOLD_STAGING_PROTECTED_URL
DAYFOLD_DEVICE_A_ACCESS_TOKEN
DAYFOLD_DEVICE_A_REFRESH_TOKEN
DAYFOLD_DEVICE_B_ACCESS_TOKEN
DAYFOLD_DEVICE_B_REFRESH_TOKEN
```

`DAYFOLD_CLOUDBASE_CLIENT_ID` 可省略，默认使用环境 ID。只有目标环境明确要求时才通过 Secret 管理设置 `DAYFOLD_CLOUDBASE_CLIENT_SECRET`。

当前 Staging-equivalent 探针：

```text
DAYFOLD_STAGING_PROTECTED_URL=https://dayfold-api-staging-317758-12-1442808051.sh.run.tcloudbase.com/v1/auth/probe
```

该服务位于 CloudBase 免费 Preview 环境，仅用于虚构账号验证，不构成独立 Staging 环境或生产批准。

不要把 Token 写在命令参数、脚本、`.env`、终端历史或报告中。应通过 CI Secret、部署平台 Secret，或终端的静默输入功能注入当前进程环境。

先在两个独立浏览器配置或设备上登录同一虚构账号，然后运行基线：

```bash
python3 -m apps.api.scripts.staging_auth_sessions baseline
```

基线要求两台设备的旧 AccessToken 均可访问 CloudBase 和 Dayfold，且
`sub` 一致。脚本允许两种 RefreshToken 契约：

```text
multi_device        两台设备均可换发
latest_session_only 仅最后登录设备可换发，较早设备返回 4xx
```

至少一台设备必须成功换发，并且新 AccessToken 必须同时通过 CloudBase
身份接口和 Dayfold 探针；两枚 RefreshToken 都被拒绝时基线失败。结果中的
`refresh_contract` 会记录实际契约。

确认注销后，在控制状态达到 `identity_disabled` 时运行：

```bash
python3 -m apps.api.scripts.staging_auth_sessions blocked
```

删除身份并确认 UID 不存在后运行：

```bash
python3 -m apps.api.scripts.staging_auth_sessions deleted
```

如果 RefreshToken 已被拒绝，脚本记录 `refresh_denied=true`。如果 CloudBase 仍签发新 AccessToken，只有该 Token 被 Dayfold 受保护探针拒绝时阶段才通过。退出码 `0` 表示通过，`1` 表示验证失败；可用 `--output <path>` 写入不含凭据的 JSON 结果。
