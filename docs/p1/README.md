# P1 文档索引

1. `../p0/`：现有资产与缺口审计。
2. `architecture-freeze/`：第一版技术架构冻结。
3. `architecture-review/`：结合中国公网访问与 Agent 评测作品集目标的复审。
4. `../../evals/memory/reports/v0.3/`：Mini v0.3 质量通过报告。
5. `dify-baseline-contract.md`：Dify Workflow 输入、输出、数据边界与验收契约。
6. `dayfold-p1-closeout-roadmap/`：P1 评测收口、剩余阻断与公网发布路线。
7. `minimal-deployment-probe-result.md`：Vercel → Render 默认域名公网链路、CORS 结果与剩余验证项。
8. `p1-final-architecture-decisions.md`：正式部署地域、备案路径、Preview 边界与 P2 进入条件。
9. `p1-managed-auth-evaluation.md`：Managed Auth 候选比较、条件性建议与最小验证要求。
10. `tencent-oneid-minimal-validation-result.md`：Tencent OneID 开通、地域、登录流程和计费验证结果。
11. `authing-free-plan-evaluation.md`：Authing 免费计划对 P2 技术验证和正式私人数据环境的适用性。
12. `authing-free-account-validation-result.md`：Authing 免费用户池、邮箱、OIDC/JWT、数据地域和删除权限验证结果。
13. `logto-tencent-shanghai-evaluation.md`：腾讯云上海自托管 Logto 的资源、成本、数据库复用与单人运维评估。

当前已冻结的模型分工：

- Chat：Doubao-Seed-2.1-Turbo
- Memory Extraction：Doubao-Seed-2.0-Mini
- Embedding：doubao-embedding-vision-251215，1024 维

P1 已完成最小部署与中国网络验证，并冻结中国大陆备案部署路径；Tencent OneID、Authing 免费计划和自托管 Logto 均已完成 P1 评估，Managed Auth 等待腾讯云正式价格裁决。

## 当前续作状态

- 已完成：评测 runner 支持 Anthropic-compatible、OpenAI-compatible 与 Dify Workflow。
- 已完成：硅基流动直连 v0.4 全量 baseline，18 个模型案例全部 100 分；p95 延迟略高于警戒线。
- 已完成：Dify Workflow v0.1 输入、输出、数据边界与验收契约。
- 已完成：Dify v0.4 全量 baseline，18 个模型案例全部 100 分，结论为通过。
- 已完成：Prompt v0.4 强化 `upsert.confidence` 必填约束，双路径 U01 稳定性测试均为 3/3 通过。
- 已完成：P1 Minimal Deployment Probe 默认域名链路，Vercel 静态页面可通过 HTTPS 调用 Render FastAPI `/health`，CORS 白名单符合预期。
- 已完成：`preview.dayfold.com.cn` 与 `api-preview.dayfold.com.cn` 的 DNS、TLS、自定义 Origin 和浏览器联调验证。
- 有条件通过：ITDOG 完成 309 个中国多运营商节点测试，294 个成功、15 个失败；中国移动、联通、电信均有 HTTP `200` 成功节点。
- 已冻结：正式生产采用中国大陆备案部署路径，主地域为中国大陆华东（上海），腾讯云作为首选备案接入商和基础设施候选。
- 已停止：Tencent OneID 高级版购买页显示 120000 元/年及 0.02 元/MAU；未购买、未创建资源、未产生费用。
- 已评估：Authing 免费计划的容量和基础认证能力足以完成虚构账号技术验证，但不满足正式身份数据地域、环境隔离、长期审计和 SLA 要求。
- 已验证：Authing 免费用户池和 OIDC/JWKS 可用，用户禁用与恢复通过；未产生费用。
- 未通过：邮箱流程受实名认证前置条件阻断，JWT 端到端与最终删除未完成，数据地域仍为 `UNKNOWN`。
- 已冻结：P2 正式身份方案采用 CloudBase Auth v2 邮箱注册、验证、密码登录与恢复；P3 先完成服务端 Token、Session 撤销和身份删除 Spike。
- 已评估：腾讯云上海自托管 Logto 能控制数据地域，但官方最低推荐为 `2C8G/256GB`，且运维负担为 Medium-High，不批准直接部署。
- 已冻结：MVP 邮件使用 CloudBase 内置邮件代发，不单独接入 SES/SMTP。
- 已冻结：正式入口使用 `www.dayfold.com.cn`，根域名永久重定向至 `www`，API 使用 `api.dayfold.com.cn`。
- 下一任务：编写 P3 实施计划；在 Production Provisioning Gate 前不购买资源。
