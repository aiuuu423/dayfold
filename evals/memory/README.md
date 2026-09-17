# Memory Evaluation

## 可复现输入

- `datasets/`：v0.1、v0.2、v0.3 虚构测试集。
- `prompts/`：对应版本的 Memory Extraction Prompt。
- `harness/`：本地评测运行器。

## 证据

- `results/`：脱敏机器结果与人工复核。
- `reports/`：HTML 可视化报告。

## P1 Provider 对照

- 火山方舟：双击 `harness/run-mini-v03.command`，运行已冻结的 Mini v0.3。
- 硅基流动：双击 `harness/run-siliconflow-v03.command`，用同一数据集和 Prompt 运行 Challenger baseline。
- 硅基流动默认模型为 `deepseek-ai/DeepSeek-V3.1-Terminus`；如账号可用模型不同，可先设置 `DAYFOLD_SILICONFLOW_MODEL`。
- 密钥优先从 macOS 钥匙串服务 `dayfold-siliconflow-api-key` 读取；没有时仅在本次终端无回显输入，不写入仓库和报告。
- Dify：双击 `harness/run-dify-v03.command`，调用已发布的 Workflow 与硅基流动直连结果对照。
- Dify Key 只从 macOS 钥匙串服务 `dayfold-dify-workflow-api-key` 读取，不回退到明文输入。
- Dify Workflow 发布时间冻结为 `2026-09-17 14:27`，内部模型为 `deepseek-ai/DeepSeek-V3.1-Terminus`。
- Dify 只接收版本化虚构案例，不复用 Dayfold 会话主键；明确删除案例继续走本地确定性逻辑。
- Dify 结果保存到 `results/dify-v03-results.json`，报告保存到 `reports/dify-v0.3/dayfold-p1-dify-v03-report.html`。

## v0.4 字段完整性复测

- `prompts/extraction_prompt_v0.4.md` 明确要求每个 `upsert` 必须包含 0–1 数值型 `confidence`，并增加目标替换示例。
- 双击 `harness/run-siliconflow-v04.command` 可复现硅基流动直连全量 baseline。
- 双击 `harness/run-dify-v04.command` 可复现 Dify Workflow 全量 baseline，并以硅基流动直连 v0.4 为对照。
- v0.4 全量结果分别保存到 `results/siliconflow-v04-results.json` 和 `results/dify-v04-results.json`。
- v0.4 报告分别保存到 `reports/siliconflow-v0.4/` 和 `reports/dify-v0.4/`。

结果文件已经移除 API Key 指纹。日志位于仓库根目录的 `local/`，默认不进入 Git。
