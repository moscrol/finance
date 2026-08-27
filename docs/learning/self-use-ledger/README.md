# 自用摩擦台账（Self-use Maturity Gate 的记账层）

> 服务对象：`docs/superpowers/specs/2026-07-11-workbench-self-use-to-invite-beta-design.md` §3.1
> Self-use Maturity Gate——「连续 10 个交易日自用 + 每日记录摩擦/失败/降级/救场 +
> 核心工作流成功率 ≥95% + 本人主观认可（一票否决）」。
> 2026-08-26 盘点确认：此前生产 runs 大头是 agent 探针与评测批跑，Gate 三项判据
> 没有一项有账可算。这个目录就是那本账。

## 怎么记（每个交易日盘后）

真人用 Workbench（:8792）做研究，每完成/放弃一个任务就记一条：

```bash
python3 scripts/self_use_ledger.py add \
  --task-type stock --question "长电科技怎么看" \
  --outcome ok --run-id run_20260826_... --minutes-saved 15
```

- `--task-type`：`market / theme / stock / news / watchlist`（对应 spec 五类核心任务）+ `other`
- `--outcome` 四态：
  - `ok` 一次性拿到可用结果
  - `degraded` 有降级/缺口但显式披露，结果仍可用
  - `failed` 没拿到可用结果（含静默错误）——必须写 `--friction`
  - `rescued` 需要人工救场（改文件/拼命令/重启）才拿到结果——必须写 `--friction`
- 会话里让 agent 代记也可以，但**只许走本 CLI**（schema 校验在写入口）。

## 怎么读

```bash
python3 scripts/self_use_ledger.py summary --days 10
```

输出按日聚合 + 三个 Gate 口径：ok 率、ok+降级可用率（§3.1.4 的 95% 用这个）、
救场条数（§3.1.5 要求日常使用不依赖人工救场）+ 五类任务覆盖缺口。

## 约定

- canonical：`docs/learning/self-use-ledger/<date>.jsonl`，唯一写入者 = `scripts/self_use_ledger.py`。
- 提交：是（Gate 验收要 git 历史作证）。md/汇总都是渲染物，不回写。
- 这里只记**真人使用**。agent 探针、评测批跑、验收 live 收据一律不进这本账
  ——混进来会把 Gate 的「本人愿意每天用」偷换成「机器每天在用」。
