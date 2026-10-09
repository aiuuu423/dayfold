# Dayfold

Dayfold 是一个面向个人长期使用的 AI 生活记录项目。它把日记和对话转化为可追溯、
可关闭、可删除的长期记忆，并在后续对话和成长洞察中按证据使用这些记忆。

当前项目处于 **Portfolio MVP 已上线、生产稳定性持续修复** 阶段，不是早期架构
设计阶段。

## 在线入口

- Web：<https://www.dayfold.com.cn>
- API：<https://dayfold-api-global.vercel.app>
- 健康检查：<https://dayfold-api-global.vercel.app/health>

公开站点是固定合成用户的 Portfolio Demo，只能使用虚构或脱敏内容：

> Demo only. Do not enter sensitive personal information.

## 当前状态

| 模块 | 状态 | 当前事实 |
| --- | --- | --- |
| Web | 已实现并部署 | 静态 HTML/CSS/JavaScript，包含 Today、Chat、Memory、Growth |
| API | 已实现并部署 | FastAPI modular monolith，生产健康检查返回 `200` |
| Today | 可用 | Entry 创建、列表、读取、编辑、软删除 |
| Chat | 可用 | SSE 流式回复、对话持久化、相关 Memory 注入 |
| Memory Extraction | 可用 | 仅提取 Event、Interest、Goal，保留来源并支持安全重试 |
| Embedding / Retrieval | 可用 | 1024 维向量、租户内 cosine retrieval、默认阈值 `0.30` |
| Memory Control | 可用 | 来源查看、Disable、确定性删除及关联数据清理 |
| Growth | 已实现，生产阻断 | 自动化测试通过；生产标准方舟请求当前 3/3 返回 `504` |
| 数据持久化 | 已上线 | 生产使用 Turso，本地可使用 SQLite |
| 公开账号体系 | 未开放 | 公开站点仍使用固定合成用户，不提供公开注册 |

截至 2026-10-09，API 自动化测试基线为：

```text
110 passed
```

当前唯一状态源见 [`PROJECT_STATE.md`](PROJECT_STATE.md)。`docs/p0` 至 `docs/p4`
及评测报告是对应日期的历史快照，不代表最新运行状态。

## 核心链路

```text
Today Entry
  → Memory Extraction
  → Embedding
  → Tenant-scoped Vector Retrieval
  → Memory-aware Chat
  → Evidence-based Growth
```

Growth 至少需要两条 Memory，且必须来自两个不同来源。证据不足时返回
“正在积累你的记录。”，不调用模型。

## 技术实现

```text
Static Web (HTML / CSS / JavaScript)
                │
                │ HTTPS / REST / SSE
                ▼
FastAPI modular monolith
  ├── Today CRUD
  ├── Chat streaming
  ├── Memory extraction and control
  ├── Embedding and retrieval
  ├── Evidence-based Growth
  └── Auth adapters
                │
        ┌───────┴────────┐
        ▼                ▼
  Turso / SQLite    Volcengine Ark
```

生产部署：

- Web：Vercel，自定义域名 `www.dayfold.com.cn`
- API：Vercel，香港区域 `hkg1`
- 数据库：Turso
- LLM / Embedding：火山方舟

## 工程边界

- 服务端强制绑定 `user_id`，客户端不能覆盖数据归属。
- 原始记录、Memory 状态和删除关系由 Dayfold 数据层管理，模型不是事实来源。
- Memory 只允许 Event、Interest、Goal 三类。
- Disable Memory 时同步移除 Embedding；Delete 时清理来源、Embedding 和失效的
  Growth 引用。
- API Key 只存在于服务端环境变量或本地钥匙串。
- 生产缺少 Turso 凭证时禁止回退到临时 SQLite。

## 已知问题

- Growth Provider 在本机使用相同标准方舟 Key、模型和 Prompt 可以成功，但从
  Vercel 香港运行时调用时仍稳定出现约 22 秒的 `504 LLM_TIMEOUT`。
- 将 Growth 改为第三次重试没有提高成功率，已撤销。
- `stream=true` 已部署验证，但生产 3/3 仍返回 `504`；问题尚未关闭，需要继续检查
  方舟 Endpoint、首包超时或运行区域链路。
- `/health` 返回的 `environment` 与 `version` 仍沿用早期探针命名，不能作为发布
  阶段标识。

## 本地验证

```bash
PYTHONPATH=. uv run --with-requirements requirements.txt \
  pytest apps/api/tests -q

PYTHONPATH=. uv run --with-requirements requirements.txt \
  python -m compileall -q app.py apps/api

git diff --check
```

模型评测和生产探针会产生真实 API 调用与费用。凭证不得写入源码、输出文件或提交历史。

## 仓库结构

```text
dayfold/
├── apps/
│   ├── web/                 # 已部署的静态 Web
│   └── api/                 # FastAPI 应用、Provider 和测试
├── docs/
│   ├── p0/ ... p4/          # 各阶段历史设计与交付记录
│   └── adr/                 # 架构决策
├── evals/memory/            # Memory Extraction 评测资产
├── PROJECT_STATE.md         # 当前状态唯一事实源
└── vercel.json              # API 部署配置
```

## 许可证

本仓库采用 [MIT License](LICENSE)。仓库中的评测案例均为人工编写的虚构数据。
