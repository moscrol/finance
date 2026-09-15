# inflight · fix/perspective-narrative-contract

权威：Gitea [#222](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/222) @ `fa58f4b4`。树 `/Users/a77/fwp-wt-perspective-narrative`。基线 `gitea/main` `d2ebf693`。

## 旧稿已收

- 脏树 `feat/reading-rules-baseline-batch1` 上未跟踪的
  `docs/superpowers/specs/2026-08-19-perspective-narrative-contract-design.md` 已删。
  与本分支只差状态行，无独有内容。
- vault 旧「待用户审阅」指针作废；以 #222 为准。

## 已验

- 契约文案 + 词表尺 + compare 单测改挂；header `startswith` 回归未改。
- 定向 pytest 46 / ruff 绿 / `merge-tree` rc=0。
- 判读基线不在本分支。§3.3.3 A 组 ≡ 直接重跑。

## 未验

- SPT 同题 live。`live_probe ask` **不能**带 `perspective_mode`，会落到中立泳道，
  读数无效。要用 sidecar + `POST /api/conversations`（`perspective_mode=single`,
  `selected_perspective_ids=["sptfei"]`），user=`linxiaoqi5111`。
- 人审「不再是填表」。
- 与 `feat/reading-rules-baseline-batch1` 的共存验证：后合的一方做。

## 范围（验收时别吵）

- 长电中立泳道本单不修，重跑仍是填表。
- compare 契约已改、线上仍不可用（1000 字帽）。
- 未切 8792。不要在脏树上改。
