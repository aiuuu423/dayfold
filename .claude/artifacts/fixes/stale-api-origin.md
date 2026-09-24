# Bug: 错误 API Origin 持久化导致 Web 无法连接

> Status: FIXED
> Mode: default
> Severity: blocker
> Last updated: 2026-09-25

## Symptom

线上页面显示 `Failed to fetch`，连接设置中保留了错误的
`https://dayfold.com.cn`，刷新页面后仍无法恢复。

## Expected

旧版保存的错误地址不应覆盖当前生产 API；新地址必须验证成功后才能持久化。

## Reproduction

- 测试：`test_web_ignores_legacy_api_origin_and_only_persists_verified_origin`
- 输入：生产站点 hostname，旧存储键指向 `https://dayfold.com.cn`
- 修复前连续 3 次失败，均错误返回网站 Origin。

## Hypotheses & diagnosis

| # | Hypothesis | Verdict | Evidence |
|---|---|---|---|
| H1 | 旧版连接设置在验证前写入 localStorage，错误地址持续覆盖生产 API | confirmed | 截图显示错误 Origin；测试稳定返回该错误值；代码先 `setItem` 后检查连接 |
| H2 | 生产 API 离线 | eliminated | `/health`、`/v1/demo`、`/v1/entries` 均返回 HTTP 200 |

## Root cause

连接设置提交时先写入 localStorage，再检查 API 是否可用。一次错误输入会成为后续启动
地址；同时旧存储键没有版本迁移，部署正确默认值后仍会被历史值覆盖。

## Fix

- 将存储键升级到 `dayfold-portfolio-api-origin-v2`，启动时清理旧键。
- 连接检查通过后才保存候选地址。
- 检查失败时恢复此前有效地址。

## Verification

- V-1：修复后回归测试通过。
- V-2：临时移除修复后测试重新失败；恢复修复后再次通过。
- V-3：API 测试套件 `108 passed`。
- V-4：JavaScript 语法与 `git diff --check` 通过。

## Regression test

- 路径：`apps/api/tests/test_health.py`
- 名称：`test_web_ignores_legacy_api_origin_and_only_persists_verified_origin`

## Pattern analysis

`git grep` 仅发现当前连接设置的一处 localStorage 写入；修复后它位于成功检查之后。

## Open questions / Follow-ups

正式账号登录、注册、会话持久化和按真实用户隔离数据尚未实现。这是认证架构任务，
不属于本次 API Origin 故障修复。
