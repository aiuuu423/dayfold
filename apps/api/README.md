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
