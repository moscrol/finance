# 判官证据投影契约（C1–C4）

- 树：`/Users/a77/fwp-wt-judge-projection`
- 分支：`fix/judge-evidence-projection-contract` @ `gitea/main` `5d7529e5`（主检出 `feat/reading-rules-baseline-batch1` 未改 verifier）
- spec：`docs/judge-evidence-projection-contract-spec.md`

## 做了什么

- C1：判官 payload 带 `title`（`MAX_EVIDENCE_TITLE_CHARS`），`detail` 不再回退 title
- C2：`evidence_id = evidence_ordinal_table()[hash]`，缺键硬失败
- C3：四处 marker-loss 全灭则 `repair_withheld=True`，保留修前 draft；`JudgeStatus` 不扩枚举
- C4：落盘 `projection_dropped_field_chars` / `truncated` / `ordinal_mismatch_count`（issued vs emitted 对称差）/ `evidence_alias_offset`

## 验证

- 定向：`test_judge_evidence_projection.py` 9 绿；`test_episode_semantic_verifier.py` + `test_session_projection.py` 随文件绿
- 变异：密排 `E{len+1}` → 编号测试红（E1 vs E3；A3 E9 变成指数卡）；去掉 title → title 测试红且 `dropped_field_chars=29`
- §8 全量 `intelligence/tests`：5141 passed / 16 failed / 11 skipped。失败全在 ceiling wiki/instruction export（`mode:entities/before.md`、leak scan），与本 diff 无 import 关系，git blob 导出读的是 HEAD 不是未提交 verifier
- §6 第 7 例：B4 冻稿投影离线已确认 E31 title 含许继/12.45（单测）。独立 grok-cli 第一发重放 175s 无输出后杀掉 → **`not_run`**，不把单测绿写成 H5 已结。

## 账本

`R-20260820-01/02` 已被 main 占用。本单 `R-20260820-03` DATA_CONTRACT、`-04` HARNESS 删格下限、`-05` 热度错绑 pending。未合未推。
