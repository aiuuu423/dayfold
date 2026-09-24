# Bug: Agent Plan 间歇性失败缺少分类与重试

> Status: RESOLVED
> Mode: --deep
> Severity: blocker
> Last updated: 2026-09-25

## Symptom

线上 Memory Extraction 偶发返回统一的 `503 LLM_UNAVAILABLE`，无法判断鉴权、
限流、上游错误、网络错误或超时，也不会对可恢复错误重试。

## Expected

只对可恢复错误执行有界重试，并返回不泄露凭证的分类错误；完整
Today → Memory → Embedding → Recall → Growth E2E 可稳定通过。

## Reproduction

- 原始线上复现：`POST /v1/memory-extractions`
- 回归测试：`apps/api/tests/test_provider_resilience.py`
- RED：模块不存在时 3/3 稳定失败
- GREEN：分类、非重试错误和最大尝试次数测试通过

## Hypotheses & diagnosis

| # | Hypothesis | Verdict | Evidence |
|---|---|---|---|
| H1 | 首次瞬时错误直接终止导致偶发失败 | confirmed | 旧 Provider 无重试；MockTransport `503 → 200` 回归测试 |
| H2 | Vercel 与北京 Agent Plan 之间连接不稳定 | confirmed | 香港 Function 两次 `10s` connect timeout，约 `22s` 返回 `LLM_TIMEOUT` |
| H3 | Turso、CORS 或数据写入失败 | eliminated | `/health`、Entries、清理请求均成功，失败发生在 Memory Provider |
| H4 | 模型本身持续不可用 | eliminated | 本机同一 Key 和轻量模型真实请求 `200`，约 `5.45s` |

## Root cause

代码层根因是 Provider 将不同上游错误折叠为统一异常，且首次失败即终止。修复后
仍存在环境层根因：Vercel 香港 Function 到北京 Agent Plan 入口间歇性连接超时；
两次有界重试仍可能全部失败。最终通过将 Memory 与 Growth 切换到标准方舟
OpenAI 兼容推理端点消除关键链路阻塞；Chat 保留 Agent Plan。

## Fix

- 新增 `apps/api/provider_resilience.py`
- Memory、Growth、Chat 共用错误分类与最多两次重试
- 仅 timeout、network、`429`、`5xx` 重试
- auth、request rejected 立即失败
- API/SSE 返回 `LLM_TIMEOUT`、`LLM_RATE_LIMITED` 等安全错误码
- 单次 Provider 超时 `80s`，总预算低于 Vercel `180s`
- Memory、Growth 改用 `/api/v3/chat/completions`
- 标准推理只接受 `DAYFOLD_STANDARD_ARK_API_KEY` 和
  `DAYFOLD_STANDARD_ARK_MODEL`，不会回退 Agent Plan
- 请求改为 `system/user` messages，响应读取
  `choices[0].message.content`

## Verification

- V-1：回归测试初始 3/3 RED
- V-2：韧性与 Provider 集成测试 `19 passed`
- V-3：API 全量测试 `107 passed`
- V-4：线上失败现在分类为 `504 LLM_TIMEOUT`
- V-5：失败验收产生的 Entry 与 Memory 已清理
- V-6：标准方舟真实探针返回 `200`
- V-7：完整线上 E2E 通过：2 Entry → 2 Memory → 2 Embedding →
  Recall 命中 2 条 → Growth 引用 2 条
- V-8：E2E 清理通过，本次创建记录残留为 0

## Regression test

- `test_bounded_post_retries_one_retryable_response_then_succeeds`
- `test_bounded_post_does_not_retry_authentication_failure`
- `test_bounded_post_stops_after_two_timeouts`
- `test_bounded_stream_retries_before_returning_response`
- 三个 Agent Plan Provider 均覆盖首请求失败、第二次成功

## Pattern analysis

代码扫描发现 `apps/api/retrieval.py` 仍有旧式 HTTP 错误处理，但它使用标准
Embedding 端点，不属于本次 Agent Plan 修复范围。

## Open questions / Follow-ups

- 持续观察 Chat 的 Agent Plan 超时率。
- 若 Chat 稳定性无法接受，再单独评估迁移到标准方舟或中国大陆异步代理。
