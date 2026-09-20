# Dayfold P1 最小部署探针验证记录

状态：默认域名与 Preview 子域名链路通过，中国三网多节点访问有条件通过
验证日期：2026-09-21
范围：P1 公网连通性验证，不代表 P2 产品或生产环境通过

## 验证链路

```text
GitHub main
    ↓
Vercel Static Preview
    ↓ HTTPS / CORS
Render FastAPI
    ↓
GET /health
```

部署提交：

```text
4c3e62e Codex/minimal deployment probe (#2)
```

公开地址：

```text
Web: https://dayfold-six.vercel.app
API: https://aiuuu423-dayfold.onrender.com
Health: https://aiuuu423-dayfold.onrender.com/health
Preview Web: https://preview.dayfold.com.cn
Preview API: https://api-preview.dayfold.com.cn
Preview Health: https://api-preview.dayfold.com.cn/health
```

## 平台调整

原设计选择 PythonAnywhere 作为 P1 FastAPI Preview。实际部署时发现当前免费账户的唯一 Web app 名额已被一个仍在维护的 Flask WSGI 站点占用；保留旧站点并新增第二个 Web app 需要升级付费套餐。

为避免删除旧站点、混合两个项目或为一次 P1 探针承担不必要的固定费用，本次将后端 Preview 调整为 Render Free。该调整只改变 P1 部署实验平台，不改变 FastAPI 应用、正式后端架构或 P2 技术方向。

## 已验证

- GitHub `main` 包含静态 Web、FastAPI `/health`、CORS 白名单和自动测试。
- Vercel 静态页面通过 HTTPS 返回 `200`。
- Render 服务状态为 `Live`，运行提交为 `4c3e62e`。
- Render `/health` 通过 HTTPS 返回 `200` 和固定 JSON。
- `https://dayfold-six.vercel.app` 获得精确的 `Access-Control-Allow-Origin`。
- 未配置的 `https://unknown.example` 不获得 CORS 允许头。
- 浏览器端从 `loading` 进入 `success`，并显示四个固定健康字段。
- `preview.dayfold.com.cn` 通过 CNAME 连接 Vercel，HTTPS 返回 `200`。
- `api-preview.dayfold.com.cn` 通过 CNAME 连接 Render，HTTPS `/health` 返回固定 `200` JSON。
- 自定义前端 Origin `https://preview.dayfold.com.cn` 获得精确的 CORS 允许头。
- 自定义域名浏览器调用从 `loading` 进入 `success`。
- Web 与 API 不包含真实用户数据、模型凭据、数据库连接或私人内容。

固定健康响应：

```json
{
  "status": "ok",
  "service": "dayfold-api",
  "environment": "preview",
  "version": "p1-probe"
}
```

## 自动验证

本地实现阶段通过：

```text
Probe tests: 8 passed
Existing Memory tests: 14 passed
Python syntax: passed
JavaScript syntax: passed
vercel.json syntax: passed
git diff --check: passed
```

## 未完成

- Render Free 冷启动条件下的用户体验记录。

## 三网拨测记录

2026-09-21 首轮尝试通过公开多节点服务验证 `https://preview.dayfold.com.cn`：

| 服务 | 结果 | 是否形成证据 |
|---|---|---|
| [ITDOG](https://www.itdog.cn/http/) | 页面提示当前使用人数已满，任务停留在 0% | 否 |
| [98CE](https://www.98ce.com/httptest) | 控制浏览器未加载测试界面 | 否 |
| [BOCE](https://www.boce.com/http/preview.dayfold.com.cn) | 游客当日免费检测次数已用完 | 否 |
| [17CE](https://203.156.197.68/?lang=zh_cn) | 控制浏览器无法建立可用页面 | 否 |

上述失败只说明第三方拨测服务当时不可用或受限，不能推导 Dayfold 在任一运营商网络中失败。当前没有足够证据将移动、联通、电信标记为通过或失败。

随后由项目负责人通过 ITDOG 完成第二轮测试并提供完整结果截图：

```text
目标：https://preview.dayfold.com.cn
完成节点：309 / 309
失败节点：15
成功节点：294
整体成功率：95.15%
全部节点平均耗时：0.380s
中国电信平均耗时：0.432s
中国联通平均耗时：0.362s
中国移动平均耗时：0.390s
```

中国电信、中国联通、中国移动均有多个节点获得 HTTP `200`，因此三网 HTTP 可达性结论为有条件通过。15 个节点失败说明当前链路不是全节点稳定，不能写成 100% 可用。

ITDOG 测试验证的是前端页面 HTTP 可达性，不执行 Dayfold 页面中的 JavaScript API 检查。自定义域名下的 Vercel → Render CORS 与 `/health` 浏览器联调已单独验证通过，但不能据此推导 ITDOG 的每个运营商节点都执行了完整交互。

## 限制

- Render Free 空闲后会休眠，首次唤醒可能超过 Web 当前 10 秒请求超时。
- 本次只证明静态页面、HTTPS、CORS 和固定健康接口可贯通。
- 本次结果不能证明 Auth、数据库、Memory、Retrieval、Chat、SSE、Worker、Agent、Safety 或生产可用性。
- Render 不因此成为 Dayfold 已冻结的生产平台。

## Preview 域名

已绑定：

```text
preview.dayfold.com.cn     → Vercel
api-preview.dayfold.com.cn → Render
```

平台默认域名继续保留，作为自定义域名故障时的独立验证入口。
