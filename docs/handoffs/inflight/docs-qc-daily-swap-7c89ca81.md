# daily-swap 第六轮独立审查

## 这个分支做什么
审查施工 c90036fa（代码 7c89ca81），只增加审查报告与离线探针；不改施工树、生产库或发布协议。

## 决策与被否方案
- 接受既有库 identity-check→replace 收窄，不要求加 stat 冒充闭合。
- 首次建库必须独立补 no-clobber 发布；否「起初不存在所以无数据可丢」，正常 DuckDB 写者在窗口提交的数据已被独立复现吞掉。
- 不合入、不授权正式换库。全文：`docs/handoffs/2026-09-13-daily-swap-round6-qc.md`。

## 当前状态
审查树 `/tmp/daily-swap-qc-7c89ca81`，只含本轮审查产物；施工分支未改。两个具体五轮修补成立，但公共链仍阻断。

## 已验证
- 干净 c90036fa 三文件 57 passed/10.07s；改动文件 Ruff 通过。
- 收据 `~/.finance-runtime/test-receipts/20260913T072926Z-c90036fa.json`（dirty=false）。
- 独立探针 3 failed：删除于 db.py:242 克隆末尾 stat、sync_daily_full.py:675 锁外 stat 均抛 FileNotFoundError；首次发布前普通 DuckDB 写者创建并提交，随后 rc=0/swapped=True 且第三方表丢失。
- 探针 `scripts/review_daily_swap_races.py`；显式运行 `python -m pytest -q scripts/review_daily_swap_races.py --tb=short`。只用临时库，当前红是缺陷证据。
- 日志 `~/.finance-runtime/reviews/daily-swap-7c89ca81/portable-probes.log`。

## 未验证 / 已知边界
未跑全量、sandbox 对照或 hithink 数据端到端；9502P/1F 仅属施工方条件收据。非协同替换的最后窗口仍在；已有边界测试不校验文字是否说过头。

## 下一步
1. P2 按文件操作边界补结构化拒绝，覆盖 clone 前中后、锁外预检与 probe 的目标消失。
2. 独立提交首次发布 os.link，无条件拒绝目标已存在；保留 WAL 检查；不得 fallback replace。测 link 成功但清理失败，此时已发布不能说生产未动。
3. 协同方按 run mutex/既有 inode SH-EX 分开定义；删「所有仓内写者」全集保证及「测试会阻止口径漂移」。施工 inflight 7665 字节需压到 ≤3K。
4. 修后独立复审、干净候选门禁全绿，再等用户授权；基线同红不等于可带红合。

## 踩过的坑
「原子换名」只保证名字切换，不保证覆盖对象仍是基线；缺失状态也需要原子条件发布。探针保存为脚本供下一轮复现，未扩通用 harness 工具，因其注入点依赖本项目函数。
