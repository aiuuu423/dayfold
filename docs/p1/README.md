# P1 文档索引

1. `../p0/`：现有资产与缺口审计。
2. `architecture-freeze/`：第一版技术架构冻结。
3. `architecture-review/`：结合中国公网访问与 Agent 评测作品集目标的复审。
4. `../../evals/memory/reports/v0.3/`：Mini v0.3 质量通过报告。
5. `dify-baseline-contract.md`：Dify Workflow 输入、输出、数据边界与验收契约。
6. `dayfold-p1-closeout-roadmap/`：P1 评测收口、剩余阻断与公网发布路线。

当前已冻结的模型分工：

- Chat：Doubao-Seed-2.1-Turbo
- Memory Extraction：Doubao-Seed-2.0-Mini
- Embedding：doubao-embedding-vision-251215，1024 维

完整 P1 仍需完成最小部署、Auth 候选和中国网络验证。

## 当前续作状态

- 已完成：评测 runner 支持 Anthropic-compatible、OpenAI-compatible 与 Dify Workflow。
- 已完成：硅基流动直连 v0.4 全量 baseline，18 个模型案例全部 100 分；p95 延迟略高于警戒线。
- 已完成：Dify Workflow v0.1 输入、输出、数据边界与验收契约。
- 已完成：Dify v0.4 全量 baseline，18 个模型案例全部 100 分，结论为通过。
- 已完成：Prompt v0.4 强化 `upsert.confidence` 必填约束，双路径 U01 稳定性测试均为 3/3 通过。
- 待验证：正式入口、部署地域、Auth 候选和中国网络最小部署测试。
