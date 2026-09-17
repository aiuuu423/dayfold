# Dayfold P1 Dify Baseline Contract

状态：Published for P1 baseline
版本：v0.1
日期：2026-09-17
发布时间：`2026-09-17 14:27`
模型：`deepseek-ai/DeepSeek-V3.1-Terminus`

## 目的

Dify 仅作为 Memory Extraction 的低代码对照组，用于回答两个问题：

1. 同一数据集、Prompt 和模型经 Dify Workflow 运行时，质量、延迟与 Token 是否发生变化。
2. Dify 在日志、会话状态、删除语义和评测可追溯性上，与 Dayfold 自有 Provider runner 有哪些差异。

Dify 不进入 Dayfold 的生产 Memory 链路，不拥有业务会话、用户档案或记忆状态。

## 验证结果

- Prompt v0.3 全量 baseline 为 `block`：关键案例 `U01` 的 `upsert` 稳定缺少 `confidence`。
- Prompt v0.4 增加字段完整性硬约束后，U01 双路径稳定性测试均为 3/3 通过。
- Prompt v0.4 全量 baseline 中，Dify 的 18 个模型案例全部 100 分，JSON 和 HTTP 成功率均为 100%，结论为 `pass`。
- 通过仅代表 Dify 满足 P1 低代码对照组门槛，不改变“不进入生产 Memory 链路”的定位。

## 应用类型

- 使用 Dify **Workflow App**，不使用 Chatflow。
- API 采用阻塞响应，便于评测器获得一次完整 JSON。
- Workflow 不开启会话记忆，不依赖 `conversation_id`。
- Workflow 内只使用人工编写的虚构案例。

## 输入契约

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `case_id` | string | 是 | 评测案例 ID，仅用于 trace 对齐 |
| `system_prompt` | string | 是 | `extraction_prompt_v0.3.md` 的完整内容 |
| `existing_memories_json` | string | 是 | 当前案例已有记忆的 JSON 数组字符串 |
| `current_input` | string | 是 | 当前用户记录 |
| `dataset_version` | string | 是 | 固定为 `dayfold-memory-pipeline-v0.3` |

请求示例：

```json
{
  "inputs": {
    "case_id": "C01",
    "system_prompt": "<extraction_prompt_v0.3.md>",
    "existing_memories_json": "[{\"id\":\"mem-1\",\"type\":\"event\",\"content\":\"...\"}]",
    "current_input": "我已经从上海搬到北京。",
    "dataset_version": "dayfold-memory-pipeline-v0.3"
  },
  "response_mode": "blocking",
  "user": "dayfold-p1-eval"
}
```

## Workflow 结构

1. Start 节点接收五个输入字段。
2. Template 节点生成用户消息：

```text
已有记忆：{{existing_memories_json}}
当前记录：{{current_input}}
```

3. LLM 节点：
   - System Prompt 使用 `{{system_prompt}}`。
   - User Message 使用 Template 节点输出。
   - `temperature = 0`。
   - 最大输出 Token 与自有 runner 保持 `300`；若 Dify 或模型不支持，再单独记录偏差。
4. End 节点只输出 `result_json`，值为 LLM 节点原始文本。

Workflow 不增加知识库检索、记忆、Agent、代码修复、JSON 重写或第二次模型调用，避免改变实验变量。

## 输出契约

Dify API 的 `data.outputs.result_json` 必须是可解析 JSON 字符串，内容与 Dayfold v0.3 输出契约一致：

```json
{
  "operations": [
    {
      "op": "upsert",
      "type": "event",
      "content": "用户已搬到北京长期居住",
      "confidence": 0.98
    },
    {
      "op": "archive",
      "target_memory_id": "mem-old-location",
      "reason": "旧居住信息已被新事实替代"
    }
  ]
}
```

允许的操作：

- `upsert`：`type` 只能是 `event`、`interest`、`goal`。
- `archive`：`target_memory_id` 必须来自当前案例的已有 Memory。
- 没有应提取内容时返回 `{"operations":[]}`。
- 明确删除案例不发送给 Dify，继续走确定性删除路径。

## Runner 映射

| Dayfold 评测字段 | Dify 字段 |
|---|---|
| `case.id` | `inputs.case_id` |
| `prompt` | `inputs.system_prompt` |
| `case.existing_memories` | JSON 序列化后写入 `inputs.existing_memories_json` |
| `case.input` | `inputs.current_input` |
| 固定数据集版本 | `inputs.dataset_version` |
| `data.outputs.result_json` | 交给现有 `parse_json_text` 与 `score_model_case` |

评测结果额外记录：

- Dify `workflow_run_id` 与 `task_id`
- HTTP 状态
- 总延迟
- Dify 返回的 token 与费用字段
- Workflow 版本
- 模型供应商与模型名

不把 Dify API Key、完整请求头或真实用户标识写入结果文件。

## 数据边界

- 只允许 `data_class = 人工定义预期结果的虚构测试数据` 的案例进入 Dify。
- 禁止传入真实日记、聊天记录、姓名、联系方式、地理轨迹或私人 Memory。
- `user` 固定使用评测标识，不使用真实用户 ID。
- 每次实验后检查 Dify 日志，只保留完成 P1 对照所需的 trace；公开报告不包含完整 Prompt 和敏感请求头。
- Dify 的日志删除不等于 Dayfold 业务删除，二者不得混用。

## 验收标准

Dify baseline 完成需要同时满足：

1. 18 个模型案例全部返回 HTTP 200。
2. JSON 成功率为 100%。
3. 使用与 Ark v0.3 相同的数据集、Prompt、温度、输出上限和评分器。
4. 两个明确删除案例继续由本地确定性逻辑处理。
5. 结果文件包含 Workflow 版本、模型、延迟、Token、失败案例和 trace ID。
6. 人工复核至少覆盖所有低于 90 分的案例，以及 3 个随机通过案例。
7. 报告明确说明 Dify 只用于 baseline，不进入生产数据链路。

## P1 决策规则

- Dify 分数高于自有 runner，不代表 Dify 进入生产链路；只能说明工作流编排没有明显损失。
- Dify 分数低于自有 runner，先检查 Prompt 注入、变量转义、输出截断和模型配置差异。
- 若 Dify 无法关闭日志或满足虚构数据隔离要求，记录为未采用方案，不再扩大接入范围。
- P1 只要求完成一次可复现 baseline，不要求把 Dify 部署为 Dayfold 的长期依赖。
