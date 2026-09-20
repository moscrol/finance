# 夜间恢复：显式刷新不能借旧成功记录验收

使用 subagent-driven-development，上一实施片Spec→Quality完成后执行。用户已授权设计复核和离线修复；本片不运行真实恢复或修改生产。

固定底 `6356ffd5e703b30948f687baaaf60102bf97f0a5`，新独占 `fix/nightly-refresh-closeout-0920`。原 `fwp-wt-nightly-review-0917` 两份未跟踪quality文件保留。解释器用主树 `.venv-workbench/bin/python`。

## 已批准修法

恢复命令明确要求 `--include-completed` 重算已完成成员。既有 `stitch_sector_members` 已返回 candidates/stitched/skipped/failed/pending_for_provider，不能只看旧 completion_audit 或CLI rc0。

以现有CLI/恢复接缝增加明确的刷新完成判据：本轮请求重算的候选全部完成，才可向恢复调用方返回成功；缺合格基线、有效成员为空、数值不足或writer失败须阻断本轮恢复成功状态。重用已有摘要和责任边界，不增加第二份freshness台账，不改审计历史，不放宽180日基线，不借未经验证名单替补。普通非刷新日更的skip→provider补齐仍按原合同运行；dry-run不能被误标为已完成写入。

## 最小验收

保留 `nightly-design/spec/probe_spec.py` 原件，在新目录用固定候选适配副本复跑R1：旧完成3板块、底表价格12、旧成员10、无180日合格基线；修前rc0且旧审计true，修后必须明确非零/刷新未完成。365日仅用于正常fixture对照，不改默认规则；对照应真正刷新三板块到12。

真实recovery.child沿该失败信号不写本轮run_id成功状态；公共staging publisher既有“不成功不发布”测试保持。补部分成功、空候选、writer失败、普通日更及dry-run对照；撤回刷新判据的单个变异须红，恢复同断言绿。运行相关有限模块及Ruff，记录测试首尾身份/命令/精确分母，日志入新独占外部目录；不得读生产库、触网、调用真实模型或复制旧大库。

提交pathspec、正常推分支、≤3KB新inflight及日期快照；独立Spec→Quality。未完整合流main或真实无人值守验证前仍是有限修复。

## 独立保留的后续合同

跨午夜回放需要同时处理源业务日证明、真实updated_at与旧snapshot_day不得取即时市值，不能单删 `qa_backfill_align.check_latest_snapshot_sources` 现有门。本片保持该安全拒绝，不宣称任意归档日重放可用。吸收main后还要只接受计划明示可选的Hithink skip，保留必需步骤与质量门的失败阻断；这不是当前旧候选R1的同一个问题。
