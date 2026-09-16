# P1 文档索引

1. `../p0/`：现有资产与缺口审计。
2. `architecture-freeze/`：第一版技术架构冻结。
3. `architecture-review/`：结合中国公网访问与 Agent 评测作品集目标的复审。
4. `../../evals/memory/reports/v0.3/`：Mini v0.3 质量通过报告。

当前已冻结的模型分工：

- Chat：Doubao-Seed-2.1-Turbo
- Memory Extraction：Doubao-Seed-2.0-Mini
- Embedding：doubao-embedding-vision-251215，1024 维

完整 P1 仍需完成 Dify + 硅基流动 baseline 和最小部署验证。

## 当前续作状态

- 已完成：评测 runner 支持 Anthropic-compatible 与 OpenAI-compatible Provider。
- 已完成：硅基流动 v0.3 一键入口，复用 Ark v0.3 的数据集、Prompt 与评分口径。
- 待真实运行：本机尚未配置 `dayfold-siliconflow-api-key`，因此没有生成或宣称 Challenger 分数。
- 待配置：Dify Workflow 输入字段与输出 JSON 契约。
- 待验证：正式入口、部署地域、Auth 候选和中国网络最小部署测试。
