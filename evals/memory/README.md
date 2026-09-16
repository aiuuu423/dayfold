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
- 硅基流动默认模型为 `deepseek-ai/DeepSeek-V3.1`；如账号可用模型不同，可先设置 `DAYFOLD_SILICONFLOW_MODEL`。
- 密钥优先从 macOS 钥匙串服务 `dayfold-siliconflow-api-key` 读取；没有时仅在本次终端无回显输入，不写入仓库和报告。
- Dify 只接收虚构或脱敏案例。接入前必须先冻结 Workflow 的输入字段和输出 JSON 契约，不复用 Dayfold 会话主键。

结果文件已经移除 API Key 指纹。日志位于仓库根目录的 `local/`，默认不进入 Git。
