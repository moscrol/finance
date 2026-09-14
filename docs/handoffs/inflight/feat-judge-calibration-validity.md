# feat/judge-calibration-validity

## 这个分支做什么

**已作废。** 接替指针 → `codex/judge-calibration-validity`（树 `/Users/a77/fwp-wt-judge-calibration-validity`，交接 `docs/handoffs/inflight/codex-judge-calibration-validity.md`）。

两条轨实施同一份 `docs/superpowers/plans/2026-09-14-judge-calibration-validity.md`，各自独立新建 `intelligence/eval/judge_validity.py`（本轨 614 行 / codex 轨 540 行），设计不同构（本轨 `IDENTITY_*`+`REASON_*` 常量+`_check_*`；codex 轨 manifest 密封+`bind_answers`/`stamp_answer`），只有 `validate_judging_batch` 同名。用户 2026-09-15 裁决 codex 轨作数。

## 决策与被否方案

| 决策 | 否了什么 | 为什么 |
|---|---|---|
| 本轨两提交不合入、不 rebase | 否了「保留本轨继续做 Task 2 下半」 | codex 轨 Task 1–5 已完成+全量 9766/0+四门反证+四叶 CI，本轨停在 Task 2 上半 |
| 只移交一处发现（P1） | 否了「整轨蒸馏成对照资产」 | 实测另两处 codex 轨已解或做法更优，无净增量 |

## 下一步（移交给 codex 轨的唯一有效发现）

**P1：`identity_state` 三态跨层无一致性断言。** codex 轨 services 层裸字面量 `llm_refine.py:459,477,1061`（`not_called`）、`:570,842`（`unreported`/`reported`）；eval 层裸字面量 `judge_validity.py:264,338,357`。两边各写各的，漂了**双向静默**：eval 层写错→全批次判不合格；services 层误设 `"reported"`→放行未验证身份。本轨补法（eval 层提 `IDENTITY_*` 常量+逐字一致测试）仍是第二事实源；正解是下沉到两层都能 import 的无依赖模块（`judge_validity` 不许 import services）。**未实施，留给 codex 轨裁决。**

## 未验证 / 已知边界

- 本轮**没跑任何测试**，结论全部来自只读比对，行号对应 codex 轨 `445058d7` / 本轨 `b9d93846`。
- 上游消息称「Task 1 三处待裁决」，本会话只见到第 3、4 处内容，第 1、2 处未追溯（见 `b4b7ee1c` 代码注释）。

## 踩过的坑

同题双轨互相看不见：inflight 按分支名索引（hook 找 `feat-*.md`，codex 那份叫 `codex-*.md`），唯一跨分支通道是项目笔记「交接记录」，但 SessionStart 注入被预算截断（实测「注入 5713 / 必读段 16423」，交接记录段落在被砍部分）。本轨 agent 因此从零重做了 Task 1。

## 已验证（只读比对，未跑测试）

- stream 身份缺口 codex 轨**已解**：`_post_chat_stream_raw(..., attempt=attempt)`，体内逐 SSE event `attempt.observe_response(event)`，取 `_served_model_from_body` 并置 `identity_conflict`。本轨该处仍是 `llm_refine.py:1955` 的「已知缺口」注释。
- 噪声底 codex 轨**做法更优**：eval 层只校验绑定（`noise_floor_missing`+`batch_id`/`judge_spec_sha256`），计算留在 `scripts/run_quality_ablation.py:661 judge_noise_floor` 单一事实源；本轨 `_recompute_noise_floor` 在 eval 层重算是第二事实源。
