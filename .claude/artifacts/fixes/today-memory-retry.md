# Today Memory Extraction 中文错误与安全重试

更新时间：2026-09-28

## 问题

Today Entry 已保存后，Memory Extraction 若超时或失败，页面直接显示后端英文错误，
且没有重试入口。再次发起提取会重新调用模型并写入新的 Memory，存在重复生成风险。

## 根因

1. Web API 客户端只保留后端 `message`，丢弃了可用于稳定本地化的 `error.code`。
2. `/v1/memory-extractions` 未按当前用户和来源检查已有结果，每次请求都会调用 Provider
   并写入新 Memory。

## 修复

- Web 保留 `error.code`，将 Memory Extraction 与 Embedding 错误映射为中文状态。
- Entry 创建成功后保留 `pendingEntryId`；失败时明确显示“记录已保存”与“重新理解”。
- “重新理解”只重跑该 Entry 的 Memory Extraction 和 Embedding，不再创建 Entry。
- API 在 Provider 调用前按 `user_id + source_type + source_id` 查询未删除 Memory；
  已存在时直接返回原结果，即使 Provider 当前不可用也不会重复调用或写入。

## 验证

- 新增 API 回归：同一 Entry 连续提取返回相同 Memory，Provider 仅调用一次，数据库仅一条。
- 新增 Web 回归：中文超时文案、重试按钮、`pendingEntryId` 和无 Entry 创建调用。
- 反向验证：临时移除 API 幂等短路后，第二次请求生成不同 Memory ID，回归测试失败；
  恢复修复后测试通过。
- 全量 API 测试：`110 passed`。
- Python 编译、`node --check apps/web/app.js`、`git diff --check`：通过。

## 边界

当前修复覆盖用户失败后发起的顺序重试。两个首次请求同时到达时，查询与写入之间仍可能
发生竞争；并发强幂等需要数据库唯一约束或独立 extraction 状态表，应作为单独设计处理。
