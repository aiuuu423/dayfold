# Dayfold

Dayfold 是一个面向个人长期使用的 AI 生活记录实验项目。它研究如何把日记、对话和成长目标转化为可追溯、可编辑、可删除的长期记忆，同时避免模型把短暂情绪、他人信息或无关细节错误地保存为用户档案。

仓库目前处于 **P1 架构与评测阶段**。前端和后端应用尚未开始正式实现；现有内容主要包括产品规格、架构决策、Memory Extraction 评测集、版本化 Prompt、脱敏结果和可复现评测工具。

## 项目目标

Dayfold 当前关注四个问题：

- 长期记忆如何从原始记录中提取，并保留来源和时间信息。
- Event、Interest 和 Goal 如何更新、归档和处理冲突。
- 用户删除原始记录时，关联 Memory 和向量如何同步退出召回。
- 模型质量如何通过固定数据集、规则评分和人工复核持续比较。

Dayfold 不把 Dify 或模型供应商作为业务事实来源。原始记录、记忆状态和删除关系由 Dayfold 自己的数据层管理；外部模型只负责受约束的生成或提取任务。

## 当前状态

| 模块 | 状态 | 说明 |
| --- | --- | --- |
| 品牌与 MVP | 已完成初稿 | 包含产品规格、交互原型和视觉方向 |
| 架构审计 | 已完成 | 已记录保留项、修订项和开放决策 |
| Memory Extraction | v0.3 通过质量门槛 | 仍有输出 Token 偏高警告 |
| Provider 对照 | 进行中 | 火山方舟已验证，硅基流动 baseline 待真实运行 |
| Web 应用 | 未开始 | 计划使用 React、Vite 和 TypeScript |
| API 与 Worker | 未开始 | 计划使用 FastAPI、Python Worker 和 PostgreSQL |
| 公网部署 | 未冻结 | 正式入口、Auth 和中国网络验证仍待完成 |

完整阶段状态见 [`docs/p1/README.md`](docs/p1/README.md)。

## 架构方向

```text
React + Vite
      │
      │ HTTPS / REST / POST SSE
      ▼
FastAPI modular monolith
      ├── Journal and Chat
      ├── Memory and Retrieval
      ├── Evaluation API
      └── Provider adapters
               │
      ┌────────┴────────┐
      ▼                 ▼
PostgreSQL          Model providers
and pgvector        Ark / SiliconFlow
      │
      ▼
Python Worker
```

当前架构原则：

- PostgreSQL 是业务数据的唯一事实来源，向量与 Memory 元数据保持同一数据边界。
- 明确删除绕过 LLM，由后端按 `user_id + memory_id` 确定性执行。
- Memory Extraction 通过异步任务运行，不阻塞原始记录保存。
- Provider adapter 隔离模型协议，避免业务逻辑绑定单一供应商。
- Dify 只用于合成数据 baseline 和工作流实验，不接收真实私人内容。

详细决策见 [`docs/p1/architecture-review/`](docs/p1/architecture-review/)。

## Memory 评测

P1 使用人工编写的虚构案例评估新增记忆、冲突归档、短暂情绪过滤、他人信息过滤和确定性删除。评测结果不包含真实用户日记。

Mini v0.3 当前结果：

| 指标 | 结果 |
| --- | ---: |
| 案例数 | 20 |
| 模型案例平均分 | 100.00 |
| JSON 合法率 | 100% |
| 关键案例通过 | 是 |
| 确定性删除成功率 | 100% |
| 延迟 p95 | 7.60 s |
| 输出 Token p95 | 743.5 |

质量阻断项已经清除，但输出 Token p95 高于 400 的预警线，因此该结果记为有条件通过。完整报告位于 [`evals/memory/reports/v0.3/`](evals/memory/reports/v0.3/)，机器结果位于 [`evals/memory/results/mini-v03-results.json`](evals/memory/results/mini-v03-results.json)。

## 仓库结构

```text
dayfold/
├── apps/
│   ├── web/                    # React + Vite 前端，P2 实现
│   └── api/                    # FastAPI 后端，P2 实现
├── docs/
│   ├── brand/                  # 品牌命名与视觉方向
│   ├── design/                 # 设计合同与历史规格
│   ├── mvp/                    # MVP 规格与交互原型
│   ├── p0/                     # 项目资产与缺口审计
│   └── p1/                     # 架构冻结、复审与阶段状态
└── evals/
    └── memory/
        ├── datasets/           # 版本化虚构案例
        ├── prompts/            # Memory Extraction Prompt
        ├── harness/            # 本地评测入口
        ├── results/            # 脱敏机器结果与人工复核
        └── reports/            # HTML 评测报告
```

`local/` 保存本地验证信息，`archive/` 保存迁移前历史文件；二者均被 Git 忽略，不属于公开仓库内容。

## 本地验证

运行不需要模型密钥的单元测试：

```bash
python3 -m unittest discover -s evals/memory/tests -v
```

运行火山方舟 Mini v0.3 评测：

```bash
./evals/memory/harness/run-mini-v03.command
```

运行硅基流动 Challenger baseline：

```bash
./evals/memory/harness/run-siliconflow-v03.command
```

模型评测会产生实际 API 调用和费用。脚本优先从 macOS 钥匙串读取密钥；密钥不得写入源码、结果文件或提交历史。

## 数据与隐私

- 仓库中的评测案例全部为人工编写的虚构数据。
- 真实日记、私人对话和用户身份信息不得进入公开评测或提交历史。
- API Key 只保存在本地安全容器或部署平台的环境变量中。
- Public Demo 只能使用虚构或充分脱敏的数据。
- 删除原始记录时，关联 Memory、来源关系和向量必须同步清理。
- 跨用户 Memory 访问属于发布阻断错误，允许值为零。

发现凭据或私人数据误入提交历史时，应立即停止公开发布、撤销凭据并清理 Git 历史，而不是只删除最新文件。

## 计划

- 完成硅基流动与 Dify baseline，形成同数据集 Provider 对照。
- 冻结正式入口、部署地域、Managed Auth 和中国网络验证方案。
- 编写 P2 Technical Specification。
- 初始化 React/Vite 前端与 FastAPI 模块化后端。
- 建立 Dayfold without Memory 与 Dayfold with Memory 的消融实验。
- 在公开前完成仓库级隐私审查和文档校对。

## 许可证

本仓库采用 [MIT License](LICENSE)。除非文件另有说明，仓库中的原创代码、评测工具、Prompt、虚构数据集和项目文档均按该许可证发布。

许可证不授予任何第三方名称、商标或外部引用材料的权利。引用外部服务和模型名称仅用于说明兼容性与实验配置。

## 命名说明

`Life Companion` 是项目早期名称，`Dayfold` 是当前名称。历史设计文件保留旧名称以维持决策可追溯性，新增代码和文档统一使用 Dayfold。
