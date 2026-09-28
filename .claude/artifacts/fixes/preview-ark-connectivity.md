# Bug: Preview 标准方舟连接超时

> Status: FIXED
> Mode: default
> Severity: blocker
> Last updated: 2026-09-28

## Symptom

Preview 环境保存日记后先返回 `503 LLM_UNAVAILABLE`；补齐 Provider 配置后，
Memory Extraction 连续返回 `504 LLM_TIMEOUT`。

## Expected

Preview 保存日记后完成 Memory Extraction 与 Embedding Sync，并显示
“已记住 1 件事”。

## Reproduction

- 页面：Dayfold `codex/formal-account-loop` Preview
- 操作：保存一条明确包含 Goal 的合成日记
- 结果：香港运行区连续两次验收均在两次有界连接重试后超时
- 配置回归测试：`apps/api/tests/test_vercel_deployment.py`

## Hypotheses & diagnosis

| # | Hypothesis | Verdict | Evidence |
|---|---|---|---|
| H1 | Preview 缺少标准方舟变量 | confirmed | 两项变量仅配置在 Production；补齐后错误由 503 变为 504 |
| H2 | 香港运行区到北京方舟端点连接超时 | confirmed | 两次独立请求均按 `10s connect timeout + retry` 失败；切换新加坡后立即成功 |
| H3 | Entry、鉴权或数据库失败 | eliminated | Entry 创建为 201，CloudBase 用户映射和 Today 读写正常 |

## Root cause

Preview 最初未加载 `DAYFOLD_STANDARD_ARK_API_KEY` 与
`DAYFOLD_STANDARD_ARK_MODEL`。补齐后，Vercel 香港运行区到北京标准方舟端点仍
连续发生连接超时；切换至新加坡运行区后同一 Provider、模型与 Key 完成真实 E2E。

## Fix

- 将现有标准方舟 Key 与 Model 扩展到 Preview。
- 将 `vercel.json` 的 API 运行区从 `hkg1` 调整为 `sin1`。
- 更新现有部署配置回归测试，锁定新加坡运行区。

## Verification

- V-1：区域配置测试在旧配置下连续失败。
- V-2：区域切换后配置测试通过。
- V-3：仅移除配置改动时测试重新失败，恢复后重新通过。
- V-4：API 全量测试 `118 passed`。
- V-5：新加坡 Preview 部署 Ready，稳定分支域名指向新部署。
- V-6：真实日记 E2E 显示“已记住 1 件事”，生成 `GOAL`，Embedding Sync 无错误。
- V-7：合成 Entry 与 Goal Memory 均已删除，页面无测试数据残留。

## Regression test

- 路径：`apps/api/tests/test_vercel_deployment.py`
- 名称：`test_vercel_configuration_targets_singapore_api_entrypoint`

## Pattern analysis

| 搜索方式 | 命中数 | 是否本次同类隐患 |
|---|---:|---|
| `git grep -n "regions"` | 2 | 否；仅部署配置与对应测试 |

## Open questions / Follow-ups

- 正式发布后继续观察标准方舟连接超时率。
- 第二账号隔离验收完成前不合并或 Promote Production。
