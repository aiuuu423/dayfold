# Dayfold CloudBase 免费环境验证结果

状态：技术验证通过，生产采用有条件通过  
日期：2026-09-22  
当前阶段：P1 Closeout  
适用范围：CloudBase 上海 PostgreSQL、pgvector、Auth、FastAPI 云托管与费用边界

## 结论

CloudBase 上海免费体验环境已经证明以下技术路径可运行：

- PostgreSQL 可连接并支持 `pgvector 0.8.2`。
- `CREATE EXTENSION vector`、余弦距离查询、HNSW 与 IVFFlat 索引均成功。
- CloudBase Auth 可以使用用户名密码创建虚构用户并签发有效 JWT。
- 现有 FastAPI `/health` 可以通过云托管容器部署并由 HTTPS 公网访问。
- CORS 继续使用 `DAYFOLD_ALLOWED_ORIGINS` 精确白名单，没有使用 `*`。
- 免费体验版不支持开启按量付费，验证过程未购买资源或产生现金费用。

该结果足以把 CloudBase 保留为 P2 正式架构首选候选，但不等于批准接入真实用户。pgvector 的长期支持、生产 Auth 边界、正式域名备案资源和 AI 服务合规仍需分别确认。

## 验证环境

| 项目 | 结果 |
|---|---|
| 环境 | `dayfold-p1-probe` |
| 地域 | 上海 |
| 套餐 | 免费体验版 |
| 订单实付 | 0.00 元 |
| 到期时间 | 2027-03-21 23:59:59 |
| 数据范围 | 仅虚构测试用户和临时向量数据 |
| 自动超额扣费 | 不支持开启按量付费 |

环境 ID、数据库连接信息、Token 和测试密码不得写入公开文档、代码或 Git 历史。本文只保留复核所需的非秘密信息。

## PostgreSQL 与 pgvector

### 基础连接

执行：

```sql
SELECT 1 AS connectivity_ok;
```

返回 `1`，证明 SQL 控制台可以连接目标 PostgreSQL。

### 版本

实例返回：

```text
PostgreSQL 17.11
pgvector 0.8.2
```

`pg_available_extensions` 中存在 `vector`，初始状态未安装。执行以下语句成功：

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

腾讯云云数据库 PostgreSQL 官方文档确认 PostgreSQL 17 对应内核版本达到要求时支持 pgvector，并提供 `CREATE EXTENSION vector`、向量距离、HNSW 与 IVFFlat 的使用说明：

- https://cloud.tencent.com/document/product/409/138219

该文档描述的是腾讯云云数据库 PostgreSQL 产品能力，不足以单独证明 CloudBase 免费版和个人版的长期产品承诺，因此仍需 CloudBase 人工工单确认。

### 向量行为

使用临时表验证：

- `vector` 类型可创建和写入。
- 余弦距离 `<=>` 返回预期排序。
- HNSW 索引创建成功。
- IVFFlat 索引创建成功。

查询结果中，相同向量余弦距离为 `0.000000`，正交测试向量距离为 `1.000000`。

验证使用 TEMP 表，没有留下正式业务表、用户数据或长期索引。

## CloudBase Auth

启用用户名密码登录后创建虚构用户：

```text
username: dayfold-p1-test
nickname: Dayfold P1 Test
```

实际登录后浏览器获得有效登录状态：

- `access_token` 存在，格式为三段 JWT。
- `refresh_token` 存在。
- Token `sub` 与测试用户 ID 一致。
- `provider_type` 为 `username`。
- `role` 为 `authenticated`。
- `is_system_admin` 为 `false`。
- Token 有明确的签发方、受众、签发时间和过期时间。

验证过程中没有把密码或 Token 写入仓库、文档或终端输出。

当前验证未覆盖：

- 邮箱验证与密码找回。
- 用户自助注销。
- 服务端 Token/JWKS 校验。
- Refresh Token 撤销。
- 身份数据备份、导出与最终删除。
- 正式 Auth 自定义域名、SLA 和生产数据地域承诺。

因此 CloudBase Auth 只通过 P1 技术闭环，不构成真实用户生产批准。

## FastAPI 云托管

新增 `apps/api/Dockerfile`，保持现有 `/health` 和 CORS 逻辑不变。云托管服务：

```text
service: dayfold-api-probe
effective deployment: 002
port: 80
runtime mode: 始终自动扩缩容
instance range: 0–5
```

默认测试域名：

```text
https://dayfold-api-probe-317758-12-1442808051.sh.run.tcloudbase.com
```

公网请求：

```http
GET /health
```

返回：

```json
{"status":"ok","service":"dayfold-api","environment":"preview","version":"p1-probe"}
```

部署环境变量：

```text
DAYFOLD_ALLOWED_ORIGINS=https://preview.dayfold.com.cn
```

CORS 验证结果：

- `https://preview.dayfold.com.cn` 获得正确的 `Access-Control-Allow-Origin`。
- OPTIONS 预检返回 `200`。
- 未知 Origin 不获得 CORS 放行头。

默认域名仅用于开发测试，不能作为正式入口或生产 SLA 证明。

## 费用与备案边界

免费体验环境完成本次验证时未产生现金费用。腾讯云 CloudBase 体验版提供免费资源点且不支持开启按量付费：

- https://cloud.tencent.com/document/product/876/127357

当前免费环境不能作为正式备案资源。腾讯云 CloudBase ICP 备案说明明确指出：

- CloudBase 静态网站托管、云函数和云托管不能作为 ICP 备案接入资源。
- 如需通过腾讯云备案，可购买满足备案条件的云开发轻量应用服务器。
- 轻量应用服务器需包月购买 3 个月及以上，备案期间剩余有效期需不少于 1 个月。
- CloudBase Run 的自定义域名必须已经完成备案；系统默认域名只用于测试，不承诺 SLA。

来源：

- https://cloud.tencent.cn/document/product/876/128405
- https://cloud.tencent.com/document/product/243/18908
- https://cloud.tencent.com/document/product/1243/77197

因此，当前免费环境只保留为技术验证环境，不能承担备案或正式公网入口。

## 人工工单

目标分类：

```text
云开发 CloudBase → 云开发-数据库
```

提交给人工工程师的问题：

1. 免费体验版和个人版 PostgreSQL 是否正式、长期支持 pgvector 0.8.2。
2. 共享实例是否允许生产环境执行 `CREATE EXTENSION vector`。
3. 扩展在维护、升级、迁移和恢复后是否保留。
4. HNSW、IVFFlat 的索引规模、内存、并发、参数和版本限制。
5. PostgreSQL/pgvector 自动升级策略与生产备份迁移建议。

当前状态：

```text
工单号：202609226778
提交时间：2026-09-22 13:27:22
人工回复时间：2026-09-22 14:25:28
工单状态：待确认结单
人工结论：RECEIVED
```

工单地址：

- https://console.cloud.tencent.com/workorder/detail?ticketId=202609226778

人工工程师回复确认：

1. CloudBase PostgreSQL 正式支持 pgvector `0.8.2`，共享实例和独享实例均可启用。
2. 允许直接执行 `CREATE EXTENSION vector`，无需另行申请权限。
3. 日常维护和内核小版本升级不会清除扩展；共享实例升级至独享实例时，扩展和索引随数据迁移保留。
4. HNSW 和 IVFFlat 均受支持，CloudBase 没有额外限制；共享实例的 CPU、内存、连接数和邻居负载会影响构建与查询稳定性。
5. 备份恢复或跨环境迁移后应重新执行 `CREATE EXTENSION IF NOT EXISTS vector`，并通过恢复脚本验证扩展和索引。
6. CloudBase 不为免费版和个人版共享实例提供 SLA，工程师明确说明共享实例适合开发测试，不适合生产核心业务。
7. 小规模生产建议升级企业版并使用独享数据库实例。
8. CloudBase PostgreSQL 原生备份功能尚在开发，当前不可用；迁移已支持 `pg_dump` / `pg_restore`。

人工答复关联的官方文档：

- https://docs.cloudbase.net/database/postgresql/pgvector
- https://docs.cloudbase.net/database/postgresql/import-data

## 采用决策

```text
CloudBase PostgreSQL technical spike: PASS
CloudBase pgvector instance behavior: PASS
CloudBase Auth username login spike: PASS
CloudBase FastAPI deployment spike: PASS
CloudBase zero-cash-cost boundary: PASS
CloudBase production adoption: CONDITIONAL
Real-user data: NOT APPROVED
```

生产采用前至少还需要：

- 完成 CloudBase Auth 服务端校验、删除和恢复流程。
- 冻结正式备案资源与域名路径。
- Production 只使用企业版独享数据库，并通过加密逻辑备份和恢复演练弥补原生备份暂不可用。
- 通过跨用户隔离、删除传播、恢复和安全测试。
- 完成隐私、AI 内容标识与生成式 AI 服务合规判断。

## 明确不变

- 不读取、迁移或接入旧 PythonAnywhere `trace_memory.db`。
- 不把真实 Journal、Chat、Memory 或身份数据写入免费环境。
- 不创建正式 Schema。
- 不改变 P1 Memory 评测资产。
- 不把 CloudBase 默认测试域名描述为正式产品入口。
