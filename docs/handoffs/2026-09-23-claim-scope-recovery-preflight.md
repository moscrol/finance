# Claim-Scope: 09-23 行情恢复只读预检

## 背景

用户在上一轮 GLM 有限独审和 L5 数据阻塞收尾后要求「执行」。本轮推进恢复前置检查，没有启动生产复盘、写库或新模型请求。产品收据仍绑定 `14f885e01f4a538492b54a27f67ab5d33b58f875`；开工文档 HEAD 为 `79f83414781cc820f4558bd34085287994f8ab55`，不把收据移签给后续文档提交。

## 按发现顺序

1. 主检出树有其他任务的未提交改动；只在干净的 `feat/claim-scope-runtime-0923` 写本轮文档。未改主检出、行情恢复分支、launchd 配置或运行代码。
2. 实际夜跑入口为 `~/.local/bin/nightly-full-review-s7.sh sync`。已安装 plist 的 `FINANCE_SYNC_CODE_ROOT` 仍为 `~/.finance-runtime/finance-sync-adcda94b5e40`，`REVIEW_SYNC_PLAN=local`。不能把磁盘上存在的 `finance-sync-2edbe4c46595` 当作已经切换的夜跑版本。
3. 当日 18:30 日志中，东财快照首次 63.0 秒失败、补偿 54.5 秒失败；异常是 `RemoteDisconnected` 后快照请求失败。当日成分行也是 0，fallback 无法补齐正式 `fact_stock_daily`。
4. 同花顺并行取数成功，日志覆盖到 09-23；但旧 local 计划声明并行表尚不投影旧复盘表。这不是「所有来源都不可用」，也不是正式行情已恢复。
5. 18:46 staging 门禁拒绝换库；20:40 finalize 的 L2 日包未到，21:05 same-day 门禁仍失败。保留原暂存库，不重跑会清理它的包装脚本。L2 失败另记，不用它替代 L5 日期一致性判据。
6. 重新在固定候选读取当前数据并求值 `health_ready` 原表达式：市场汇总 09-22、快照 09-23，`market_data_consistent=false`。生产 `/api/health` 返回 200，七项身份与上一轮一致；存活正常不代表 readiness 恢复。本轮未重调完整 readiness。
7. 恢复线已由他人推进到 `f22cd22b6`，且有其他人的未提交文件。旧 HOLD/全量红交接不能冒充新提交验收；本轮未使用该枝、未重跑其门禁，也没有接管其进程。

## 决策与被否方案

| 方案 | 评价 | 结果 |
|---|---|---|
| 先做只读定位，保留 K3 首发 | 尚未满足候选数据判据；能定位实际写者与失败路径 | 已执行 |
| 自动重跑生产复盘或绕调 sync/recovery 脚本 | AGENTS/CLAUDE 明确要求用户手动 `/daily-full-review`；且会触及现存失败 staging | 未执行，等手动入口 |
| 把并行表最新日期当正式表已恢复 | 夜跑源码与失败日志均不支持这个结论 | 否决 |
| 把旧恢复线签字移到 f22 或合并 Claim-Scope 求绿 | 新候选须有自己的门禁，代码合并也不会自动补齐数据 | 否决 |

## 收据与边界

树外证据根：`~/.finance-runtime/reviews/claim-scope-runtime-20260923/recovery-preflight-01/`。

- `check-inputs.py` / `data-consistency.json`：只读候选判据，DB 文件元数据和快照哈希在检查前后稳定；不是完整数据库冻结或完整 readiness。
- `production-health.json`：当前生产七身份字段一致，代码仍 `3b7e473575b0ff2dea3c1088ba7b5e330e95c8e4`、`continuous_glm/glm-5.3-flash`。
- `nightly-20260923.out.txt` / `eastmoney-failure-excerpt.txt`：从现有日志摘取；这些历史外呼不是本轮请求。
- 无新产品改动，不重跑全量工程或独审；K3 两题仍各首发 0、重发 0、续问 0。未冻数据、未起旁路、未写生产、未合并、未部署。
- 工具盘点：复用原候选 AST 判据检查形状，诊断脚本绑定本批证据保存于树外。没有新增通用恢复入口或改变能力，因此不新增 harness-reference 工具，也不更新能力图。

## 下一步

用户手动 `/daily-full-review 2026-09-23` 后，按既有流程核对当日恢复方案与当前数据写者；若须采用恢复分支或补 09-21 历史，先落实对应合同、当前候选门禁和发布授权，不能沿用旧分母决定或旧签字。临时库验收通过后才可换库，之后重新验证日期一致性和完整 readiness，再恢复 K3 条件卡流程。手动调用本身不保证恢复通过。
