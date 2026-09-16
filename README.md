# Dayfold

Dayfold 是一个以长期记忆、数字档案和个人成长记录为核心的私人生活产品。

当前仓库处于 P1 技术架构冻结阶段，尚未开始正式业务实现。仓库包含品牌与 MVP 设计、架构决策、模型评测集、脱敏结果和可复现评测工具。

## 目录

- `apps/web/`：React + Vite + TypeScript 前端，待 P2 实现。
- `apps/api/`：FastAPI 后端，待 P2 实现。
- `docs/brand/`：品牌命名与视觉方向。
- `docs/mvp/`：MVP 规格和交互原型。
- `docs/design/`：设计合同与历史规格。
- `docs/p0/`：Phase 0 项目审计。
- `docs/p1/`：Phase 1 架构冻结与复审。
- `evals/memory/`：版本化 Prompt、虚构测试集、脱敏结果和评测工具。
- `local/`：本地验证脚本与日志，不进入 Git。
- `archive/`：历史压缩包和冗余交付物，不进入 Git。

## 当前模型决定

- Chat：Doubao-Seed-2.1-Turbo
- Memory Extraction：Doubao-Seed-2.0-Mini
- Embedding：doubao-embedding-vision-251215，1024 维
- 明确删除：后端按 `user_id + memory_id` 确定性执行

## 数据边界

- 评测数据均为人工定义预期结果的虚构案例。
- 真实私人日记不得进入公开评测、Dify 或仓库。
- API Key 只保存在本地安全容器或部署平台环境变量中。
- 删除原始记录时，关联 Memory 和向量必须同步清理。

## 品牌命名说明

`Life Companion` 是早期项目名，`Dayfold` 是当前品牌名。历史文件保留原名以维护设计决策的可追溯性，新增代码和文档统一使用 Dayfold。
