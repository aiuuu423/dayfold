# 腾讯云上海自托管 Logto 评估

状态：完成公开资料评估，不批准部署  
日期：2026-09-21  
当前阶段：P1 Closeout  
适用范围：正式 Auth 候选的资源、成本和运维负担

## 结论

腾讯云上海自托管 Logto 在技术和数据地域上可行，但不符合 Dayfold 当前的低成本、低运维目标。

Logto OSS 使用 MPL-2.0 许可证，不收取软件许可证费；但官方给出的最低推荐资源是 `2 vCPU / 8 GiB / 256 GiB`，并要求 PostgreSQL、HTTPS 反向代理、邮件连接器、数据库迁移和持续升级。它不是可以无成本附加到小型 FastAPI 主机上的轻量组件。

当前裁决：

```text
Data region control: PASS
OIDC / OAuth capability: PASS
License cost: PASS
Minimum resource fit: FAIL
Operational simplicity: FAIL
Exact Tencent cost: NOT QUOTED
P2 deployment approval: REJECT
```

不购买腾讯云资源，不初始化 Logto，不修改 Dayfold 业务代码。

## 官方资源要求

Logto 官方 OSS 文档给出的最低推荐硬件为：

```text
vCPU: 2
Memory: 8 GiB
Disk: 256 GiB
```

同时要求：

- Docker 或 Node.js。
- PostgreSQL 14 或更高兼容版本。
- Core 服务端口 `3001`。
- Admin Console 端口 `3002`。
- 生产环境独立 PostgreSQL。
- HTTPS 反向代理。

来源：

- [Logto OSS Get started](https://docs.logto.io/logto-oss/get-started-with-oss)
- [Logto OSS Deployment and configuration](https://docs.logto.io/logto-oss/deployment-and-configuration)

官方特别说明示例 `docker-compose.yml` 只用于演示，因为它内置临时 PostgreSQL，重复执行可能创建新数据库并丢失原数据。Dayfold 不得把演示 Compose 直接用于生产。

## 最小拓扑

### 可接受拓扑

```text
Internet
   ↓
Tencent Cloud Shanghai
   ↓
Nginx / HTTPS
   ├── auth.dayfold.com.cn → Logto Core :3001
   └── internal admin route → Logto Admin :3002
                         ↓
TencentDB PostgreSQL
   ├── dayfold database
   └── logto database
```

要求：

- Logto 与 Dayfold API、Worker、PostgreSQL 保持上海地域。
- 数据库实例可以复用，但 Logto 必须使用独立数据库和独立数据库用户。
- Logto 不与 Dayfold 共用表、Schema、迁移历史或数据库凭据。
- Admin Console 不直接面向公众开放。
- 安全组只允许必要端口。
- PostgreSQL 只走私有网络。
- `DB_URL`、密钥和 SMTP 凭据存储在部署平台 Secret 或安全凭据系统中。

### 不采用拓扑

```text
Single 2C2G server
├── FastAPI
├── Python Worker
├── Logto
└── PostgreSQL
```

该拓扑低于 Logto 官方最低内存建议，并把 API、身份、Worker 和数据库放进一个故障域。它不能作为正式生产方案。

## PostgreSQL 复用

Logto 官方建议使用新的空数据库，但不强制独占整个 PostgreSQL 实例。

因此可以复用 Dayfold 计划中的腾讯云 PostgreSQL 实例，降低重复购买数据库的成本：

```text
PostgreSQL instance
├── database: dayfold
│   └── owner: dayfold_app
└── database: logto
    └── owner: logto_app
```

必须保持：

- 两套数据库用户互不可访问。
- Logto 不安装 `pgvector` 业务对象。
- Dayfold 业务迁移不触碰 Logto 数据库。
- Logto alteration 只对 `logto` 数据库执行。
- 备份恢复必须能分别验证两套数据库。

腾讯云 PostgreSQL 总费用由规格、存储、备份超额、日志和流量组成；官方要求通过登录后的价格计算器获得准确报价。[腾讯云 PostgreSQL 计费概述](https://cloud.tencent.com/document/product/409/49577)

## 计算资源

### 独立 Logto 主机

按官方最低建议，需要至少：

```text
2 vCPU
8 GiB RAM
256 GiB disk
```

优点：

- 身份服务与 Dayfold API、Worker 隔离。
- Logto 故障不会直接耗尽 Worker 资源。
- 升级和回滚边界清楚。

缺点：

- 增加一台长期运行实例。
- 增加系统盘、带宽、监控和备份成本。
- 增加一套主机补丁和告警。

### 与 Dayfold 主机共用

如果与 FastAPI 和 Worker 共用主机，机器规格必须在 Logto 官方最低建议之上预留 Dayfold 自身资源。由于 P2 尚未做容量测试，当前无法冻结共享主机规格。

共享主机只能作为后续容量实验，不作为本次正式建议。

## 成本模型

### 固定软件费用

| 项目 | 固定软件费用 |
|---|---:|
| Logto OSS | 0 元 |
| OIDC / OAuth | 包含 |
| Admin Console | 包含 |
| 用户目录 | 包含 |

Logto 仓库使用 MPL-2.0 许可证。[Logto GitHub](https://github.com/logto-io/logto)

### 云资源费用

```text
每月总成本
= 计算实例
+ 系统盘 / 数据盘
+ 公网带宽或流量
+ PostgreSQL 增量
+ 备份超额
+ 日志
+ 邮件发送
+ 域名与证书可能产生的费用
```

当前不能给出可靠的固定人民币月价，原因是：

- 腾讯云 CVM 价格取决于上海可用区、机型、包年包月或按量、磁盘和带宽。
- 账号新客优惠不能作为长期续费成本。
- 腾讯云官方要求使用登录后的价格计算器确认组合价格。
- PostgreSQL 是否已作为 Dayfold 正式数据库购买，会改变 Logto 的边际成本。

腾讯云 CVM 支持包年包月和按量计费；包年包月通常更适合长期稳定业务，按量计费单价通常更高。[腾讯云 CVM 计费模式](https://cloud.tencent.com/document/product/213/2180)

### 成本判断

如果 Dayfold 尚未购买满足 `2C8G/256GB` 以上余量的正式主机，Logto 会引入明显的新增固定成本。

如果 Dayfold 已经拥有足够余量的正式主机和托管 PostgreSQL，Logto 的边际现金成本可能主要来自邮件与资源增配，但仍有不可忽略的运维成本。

在取得腾讯云账号实际报价前，不能证明自托管 Logto 比每月 139 元的 Authing 基础版更便宜。

## 邮件成本与配置

Logto 不提供免费的生产邮件基础设施。邮箱注册、验证码登录和密码重置需要配置邮件连接器。

Logto 官方提供通用 SMTP 连接器，要求：

- SMTP host 和 port。
- 发件邮箱。
- SMTP 用户名与密码或 OAuth2。
- `Register`、`SignIn`、`ForgotPassword` 等模板。

来源：[Logto SMTP Connector](https://docs.logto.io/integrations/smtp)

腾讯云 SES 支持 SMTP，可与 Logto SMTP Connector 对接。腾讯云 SES 为按量计费、日结后付费，实际价格需要以 SES 价格说明和账号控制台为准。[腾讯云 SES 产品概述](https://cloud.tencent.com/document/product/1288/47445)

这意味着即使 Logto 软件免费，邮箱流程仍然不是零成本，也需要：

- 发信域名 DNS。
- 发信地址。
- 邮件模板审核与维护。
- 退信和投诉处理。
- SMTP 凭据轮换。
- 送达率监控。

## 运维负担

### 部署

- 安装 Docker 或 Node.js。
- 准备 PostgreSQL。
- 使用 Logto CLI 初始化数据库。
- 配置 `ENDPOINT`、`ADMIN_ENDPOINT`、`DB_URL`。
- 配置 Nginx 和 HTTPS。
- 配置 Admin Console 网络边界。
- 安装并持久化 Connectors。
- 配置 SMTP。

### 升级

Logto 升级不只是替换容器镜像。官方文档要求数据库 alteration 在单实例中执行：

```text
npm run alteration deploy latest
```

因此每次升级至少需要：

1. 阅读 release notes。
2. 备份 Logto 数据库。
3. 在隔离环境验证 alteration。
4. 执行数据库迁移。
5. 更新容器。
6. 验证 OIDC Discovery、JWKS、登录、刷新和登出。
7. 准备数据库与容器回滚方案。

来源：[Logto Deployment and configuration](https://docs.logto.io/logto-oss/deployment-and-configuration)

### 日常维护

- 操作系统和 Docker 安全补丁。
- Logto 安全版本跟踪。
- PostgreSQL 备份与恢复演练。
- TLS 证书续期。
- SMTP 送达率和额度。
- 资源利用率和磁盘告警。
- 登录失败、暴力破解和异常 Token 监控。
- Secret 与 OIDC 私钥轮换。
- 账号删除和导出验证。
- 故障响应。

### 单人项目影响

运维复杂度评级：

```text
Medium-High
```

身份服务是所有用户进入 Dayfold 的前置依赖。Logto 不可用时，即使 Journal、Chat 和 Memory 正常，用户也可能无法登录。自托管把可用性、安全升级和事故响应全部转移给项目负责人。

## 安全边界

自托管 Logto 能解决数据地域控制，但同时增加安全责任：

- 用户密码哈希与身份资料存储在自有 PostgreSQL。
- `DB_URL`、SMTP 密码、OIDC 私钥和 Secret Vault KEK 必须安全存储。
- Admin Console 只能由受控网络访问。
- 生产镜像必须固定版本，禁止直接长期使用 `latest`。
- 升级前必须验证数据库迁移。
- 删除 Logto 用户前，仍要先执行 Dayfold 业务数据删除传播。

Logto 的用户 ID 仍然不能作为 Dayfold 业务主键。正式映射保持：

```text
Logto sub
    ↓
Dayfold identity mapping
    ↓
Dayfold internal user_id
```

## 与 Dayfold 原则的匹配

| 原则 | 结果 |
|---|---|
| 中国大陆数据地域 | 满足 |
| 零 Auth 许可证费 | 满足 |
| 低云资源成本 | 未证明 |
| 低运维复杂度 | 不满足 |
| OIDC / PKCE | 满足 |
| 邮箱注册与重置 | 需要额外 SMTP |
| 用户删除控制 | 可控，但需自行验证 |
| 单人项目适配 | 较弱 |
| Simple over Sophisticated | 不满足 |

## 决策

不批准在当前 P1 或 P2 MVP 直接部署腾讯云上海 Logto。

原因：

1. 官方最低推荐资源高于轻量单机假设。
2. 软件免费不代表计算、数据库、邮件和备份免费。
3. 升级包含数据库 alteration，运维责任明显。
4. 自托管 Auth 会成为新的关键生产系统。
5. 当前没有腾讯云上海实际长期报价。
6. 当前也没有 Logto 与 Dayfold 共机的容量证据。

Logto 保留为条件候选：

```text
只有当
腾讯云实际报价可接受
并且
项目负责人接受 Medium-High 运维责任
并且
完成恢复与升级演练
才重新评估部署
```

## 下一步

下一项最小任务不是部署 Logto，而是取得不购买的腾讯云正式报价：

```text
1. 上海 CVM 2C8G + 256GB
2. 上海 PostgreSQL 最低正式规格
3. 现有 PostgreSQL 增加独立 logto database 的边际成本
4. 腾讯云 SES 小规模事务邮件成本
5. 包年包月续费价，不使用一次性新客价
```

报价确认后，再与 Authing 基础版每月 139 元进行同口径比较。
