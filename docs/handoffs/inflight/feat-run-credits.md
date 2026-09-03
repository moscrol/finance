# feat/run-credits

树 `~/fwp-wt-credits`，基座 `gitea/main`=`78fb8639`。用户 09-03 口述：「额度一开始是我赠送，后面是充值的月度额度」。

## 这个分支做什么
每用户额度账本 `intelligence/api/credits.py` `CreditStore`：`gift`（赠送，默认不过期）+ `monthly`（月度充值，默认
30 天到期），按 run 计；首次提问自动赠送 `WORKBENCH_CREDITS_SIGNUP_GIFT` 次；运营 CLI `scripts/workbench_credits.py`
（grant / balance / list / revoke / history）；`GET /api/credits`；bootstrap 带 `credits` 摘要；会话栏页脚显示余额
（`ConversationList`，受理/收口时刷新）。接进 `/api/runs` 与对话消息两条路径：`_reserve_run_budget` 先占钱包再占日配额，
任一拒绝退另一道；准入拒收与落盘失败也退。手册 `hosted-alpha-gate.md` §1.5 / §4.2 / §4.3。

## 决策与被否方案
- 先到期先扣、不过期最后扣、同到期 FIFO / 否「赠送先用」/ 月度是买来这个月用的，不该被赠送挤掉
- 自动赠送判据 = 没有账本文件 / 否「余额为 0」/ 后者用完会再送
- 坏账本 fail closed（503 + 不改写）/ 否照 quota 当空账本 / 钱的账本清零重建等于再送一次
- flock 文件锁 + 进程内锁 / 否只进程内锁 / CLI 与服务进程同写一份账本会丢更新（变异实测）
- 429 不带 Retry-After / 否 86400 / 不是等一会就有
- run 失败不自动退 / 否按 error 分类退 / 分不清谁的锅，owner `grant` 补偿
- 单位仍 run / 否 token / §4.3 边界不变；默认关（`WORKBENCH_CREDITS` 不设 = 历史行为）
- fetch 层解 `{"detail"}` / 否原样 / 此前 429 横幅直接显示整段 JSON

## 已验证（本树、`.venv-workbench`）
- `test_api_credits.py` 22 例；相关 7 个 API 文件 192 绿；干净树全量 7541P/5F（5 红=基线 dream_mine），收据
  `20260903T065357Z-f8378bc8` ✅ 可采信
- webapp lint / typecheck / vitest 75（+4）/ build；bundle 已重建入库
- 五组变异全红：去 flock（跨进程 2/2 红）/ 颠倒消费顺序（3 红）/ 坏账本 fail open / 日配额拒绝不退额 / 忽略过期
- live 干跑 8899：gift=2 两问 200 第三问 429；服务不停 CLI 充 3 → 三问 200 再 429；run 恰 5 条；owner 豁免
- pre-commit 11 道（`granted_at` 曾被「写了没人读」拦下 → 加 FIFO 读取点，不加白名单）

## 未验证 / 已知边界
- 未部署（8792 仍 `c88c81da5120`）、未开 `WORKBENCH_CREDITS`；`alpha.env` 已加两行（gift=30 占位，数字用户定）
- 无支付集成：充值 = owner 收款后手工 `grant --kind monthly`；将来回调调同一函数
- `components/Sidebar.tsx` 是无人引用的死组件，没动
- 刻意不碰 PR #550 改动的 §1.2/§2/§3/§6/§7 与 `inflight/main.md`；与 main、#550 merge-tree 均 clean

## 下一步
1. 用户定赠送数与月度额度数 → 合入 → 随下批切流上 8792（bundle 已在本 PR 里，切流不用再 build）
2. 支付回调 / 用户自助充值页（Beta）

## 踩过的坑
- multiprocessing.Pool 版跨进程测试在整文件里偶发挂死（与 pytest 线程共存），改 subprocess 后连跑稳定
