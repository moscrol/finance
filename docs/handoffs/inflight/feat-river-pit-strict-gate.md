# feat/river-pit-strict-gate · 工单 #43（OPT-01 第一刀）

## 这个分支做什么
`river.sector_recorded_at_sql` 不再 `LEAST(updated_at, 名单快照 captured_at)`，只用这一行自己的 `updated_at`。堵的反例：T 日 1%、T+7 被 sync 覆盖成 9%，同 generation 下 `captured_at` 不动，河把 9% 标成 T 日 strict。工单 `2026-09-08-river-content-recorded-at-strict-gate-workorder.md`；上游补强 spec PR #680 OPT-01。

## 决策与被否方案
- 去掉台账作证、接受覆盖面缩水；否了「只在 updated_at ≤ C 时用 captured_at」——那种情况 updated_at 自己已够 strict，captured_at 唯一能多给的天恰恰是不成立的那些。
- 反转了 09-06 的测试 `test_dirty_updated_at_recovered_from_ledger`（原假设「重发布不改内容」）；否了保留旧测试加新测试并存——两者互斥，留着就是两套口径。
- 删了 `sector_ledger_join` / `_has_table`（河里唯一用途消失）；否了留空壳兼容——审计脚本是唯一外部调用方，同分支改掉。
- 不做内容版本存储（hash / 有效期 / `published_at`）；否了顺手加列——那是 writer 合同的事，走 `2026-09-05-river-recorded-at-workorder.md`。
- roadmap G-02 行追加 09-08 撤回一句（一行，不整文件覆盖他人在途改动）。

## 当前状态
已提交 `07857c80`（`river.py`、审计脚本、测试重写、工单 + INDEX #43 行 + roadmap 一行），基线 gitea/main `f90af450`。PR 号见本文件提交后的 PR。

## 已验证
- river 七个测试文件 38 passed / 44 skipped；新夹具对旧 `river.py` 6 红；ruff 0；pre-commit 全 Passed；审计脚本 `--help` 可跑。
- **生产库只读实测（09-08 晚，同一库两版代码）**：`fact_sector_daily` strict 21 → 1 天，`fact_sector_stock_daily` 50 → 48，六轨联立 strict 重放 **16 → 1 天**（只剩 2026-09-07）。缩水的天全是名单 `captured_at` 撑起来的。

## 未验证 / 已知边界
- 合入后回放 / 校准里 `require_strict` 的消费方能用的历史只剩 1 天——这是把假 strict 拿掉的真实底数，不是回归；但**合并时机要用户拍**（可与内容级 `recorded_at` 一起上）。
- 未跑全量 pytest；`slice_river` 端到端（需真库文件）走的是既有 skip 用例，未新增。
- OPT-01 验收 1 的后半「T+7 查询能看到修订与原版本关系」需要内容版本存储，本单不做。
- 09-06 spec §2.3 与 BP 里引用的「16 天 strict」数字已失效，那两份文件在主检出树有他人未提交改动，未改，需对齐时逐条移植。

## 下一步
1. 用户拍板合并时机；合后 INDEX #43 行改 ✅。
2. 开 `2026-09-05-river-recorded-at-workorder.md`（写一次不更新的内容 `recorded_at`），这是把覆盖面正当拿回来的唯一路。
3. 合后用 `scripts/river_pit_audit.py --json` 重量一次记进交接。

## 踩过的坑
- 生产库只读连接可开（写锁只挡写），审计不到 1 秒；别因为「有锁」放弃量数。
