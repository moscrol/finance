# feat/run-credits

树 `~/fwp-wt-credits`，基座 `gitea/main`=`78fb8639`。用户 09-03 两次口述：「额度一开始是我赠送，后面是充值的月度额度」；
「一次 session 耗费多少积分得有个算法；送积分一开始 2000，20 元 = 2000 积分」。

## 这个分支做什么
每用户**积分账本**（100 积分 = 1 元）`intelligence/api/credits.py`：`CreditPricing`（价目表，`WORKBENCH_CREDITS_PRICING`
JSON，内置占位）+ `read_run_usage`（从 `continuous-episode.json` 按 `served_model` 读 token）+ `CreditStore`
（`gift` / `monthly` grant、预占 `reserve→bind_hold→settle`、欠账、flock）。首次提问自动赠送 `SIGNUP_GIFT`（2000）。
算法：`points = max(ceil((base + markup×Σ token费 + 工具费)×100), min)`；零用量未完成 = 0，完成无用量 = base。
`app.py`：`_reserve_run_budget` 返回 hold_id → `create_run` 后 `_bind_run_budget`；`RunSupervisor.on_settle` 在 `_forget`
（worker 返回 / 排队取消）结算；`GET /api/credits`；bootstrap `credits` 摘要；会话栏页脚显示积分与元。
运营 CLI `scripts/workbench_credits.py`：grant(`--points|--yuan`) / balance / list / revoke / history / **pricing / estimate**。
手册 §1.5 / §4.2 / §4.3。

## 决策与被否方案
- 预占→结算 / 否提交即扣固定数 / 用量只有跑完才知道；预占只占可用余额不动 grant（grant 会过期）
- 可用 > 0 即受理，透支记欠账 / 否要求余额 ≥ 预占 / 「还剩 3 分为什么不让我用」；欠账阻断新提问、下笔 grant 先抵
- 烧了 token 的失败照收 / 否失败全退 / 分不清谁的锅，按实际发生记，owner `grant` 补偿；零用量未完成免费
- 价目表元/百万 token + markup 单列 / 否直接写积分费率 / 与供应商报价同口径，成本利润分开看
- 预占 TTL 6h / 否永久 / 崩在 reserve 与 bind 之间的孤儿预占不能永远占余额
- 先到期先扣、不过期最后扣、同到期 FIFO；坏账本 fail closed；flock；默认关——与首版一致

## 已验证（本树、`.venv-workbench`）
- `test_api_credits.py` **37 例**（定价 7 / 用量读取 2 / 账本 15 / API 8 / CLI 3 / 跨进程 1）
- **八组变异全红**：去 flock / 透支不记欠账 / 结算不释放预占 / 忽略模型费率 / 向下取整 / 执行器终态不结算 / 充值不抵欠账 / 罐头与失败不分
- webapp lint / typecheck / vitest 75 / build；bundle 已重建入库
- 真实生产 run（37,256 in / 792 out @ glm-5.3）按占位价目 = 35 积分；2000 积分 ≈ 57 次
- pre-commit 11 道（Settlement / CostBreakdown 字段曾被「写了没人读」拦下 → 结算日志 + 协议序列化读取点，不加白名单）

## 未验证 / 已知边界
- 未部署（8792 仍 `c88c81da5120`）、未开 `WORKBENCH_CREDITS`；本地 `alpha.env` 已是 gift=2000，`pricing.json` 样例已放
  `~/.local/share/finance-workbench/pricing.json`（占位数字，用户按供应商报价改）
- 判官（grok-cli）token 没进 episode，未计费；legacy `/api/runs` 路径无 episode 时只收 base
- 无支付集成：充值 = owner 收款后 `grant --kind monthly --yuan N`；将来回调调同一函数
- 刻意不碰 PR #550 改动的 §1.2/§2/§3/§6/§7 与 `inflight/main.md`

## 下一步
1. 用户定价目表数字（markup / 费率 / 基础费）→ 合入 → 随下批切流上 8792（bundle 已在 PR 里）
2. 支付回调 / 用户自助充值页；判官 token 入账（Beta）

## 踩过的坑
- multiprocessing.Pool 版跨进程测试与 pytest 线程共存偶发挂死 → 改 subprocess
- 测试价目算术错三处（5000 token ≠ 50 分）→ 先用 `estimate` 算再写断言
