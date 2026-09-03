# feat/run-credits

树 `~/fwp-wt-credits`，基座 `gitea/main`=`78fb8639`。用户 2026-09-03 口述需求：「用户的额度，一开始是我赠送部分，
后面就是充值的月度额度」。

## 这个分支做什么
每用户额度账本 `intelligence/api/credits.py` `CreditStore`：`gift`（赠送，默认不过期）+ `monthly`（月度充值，默认
30 天到期）两类 grant，按 run 计；首次提问自动赠送 `WORKBENCH_CREDITS_SIGNUP_GIFT` 次；运营 CLI
`scripts/workbench_credits.py`（grant / balance / list / revoke / history）；`GET /api/credits`；bootstrap 带 `credits` 摘要。
接进 `/api/runs` 与对话消息两条路径：`_reserve_run_budget` 先占钱包再占日配额，任一拒绝退另一道；准入拒收与落盘失败也退。
手册 `hosted-alpha-gate.md` §1.5 / §4.2 / §4.3。

## 决策与被否方案
- 先到期先扣、不过期最后扣、同到期 FIFO / 否「赠送先用」/ 月度是买来这个月用的，不该被赠送挤掉
- 自动赠送判据 = 没有账本文件 / 否「余额为 0」/ 后者用完会再送
- 坏账本 fail closed（503 + 不改写）/ 否照 quota 当空账本 / 钱的账本清零重建等于再送一次
- flock 文件锁 + 进程内锁 / 否只进程内锁 / CLI 与服务进程同写一份账本会丢更新（变异实测）
- 429 不带 Retry-After / 否 86400 / 不是等一会就有
- run 失败不自动退 / 否按 error 分类退 / 分不清谁的锅，owner `grant` 补偿
- 单位仍 run / 否 token / §4.3 边界不变，定价按最贵档位估
- 默认关（`WORKBENCH_CREDITS` 不设 = 历史行为）/ 否默认开 / 与并发守卫同纪律

## 已验证（本树、`.venv-workbench`）
- `test_api_credits.py` 22 例（账本 13 / API 6 / CLI 2 + 跨进程 1）；相关 7 个 API 测试文件 192 绿
- 五组变异全红：去 flock（跨进程用例 2/2 红）/ 颠倒消费顺序（3 红）/ 坏账本 fail open / 日配额拒绝不退额 / 忽略过期
- ruff check + format；pre-commit 11 道（`granted_at` 曾被「写了没人读」拦下 → 加 FIFO 读取点，不是加白名单）
- multiprocessing.Pool 版跨进程测试在整文件里偶发挂死（与 pytest 线程共存），改 subprocess 后连跑稳定

## 未验证 / 已知边界
- 未部署（8792 仍 `c88c81da5120`）、未开 `WORKBENCH_CREDITS`；`alpha.env` 已加两行（gift=30 是占位，数字由用户定）
- 前端未展示余额（bootstrap 已给 `credits.remaining`，UI 另开）
- 无支付集成：充值 = owner 收款后手工 `grant --kind monthly`；将来回调调同一函数
- 手册 §1.5 插在 §1.4 与 §1.3 之间、§4 改两条，刻意不碰 PR #550 改动的 §1.2/§2/§3/§6/§7 与 `inflight/main.md`，避免冲突

## 下一步
1. 用户定赠送数与月度额度数（默认 30 / 200 只是示例）→ 合入 → 随下批切流上 8792
2. 前端余额显示（Sidebar 读 `bootstrap.credits`）
3. 支付回调 / 用户自助充值页（Beta）
