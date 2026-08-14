# 2026-08-14 L3 低信号公告 + 空集假证据 — 已合 main

PR [#346](https://github.com/linxiaoqi5111-del/finance-workspace-private/pull/346) 已合入 `main`（merge `6be57845`，修复提交 `c453a851`）。**未切 8792。**

## 做了什么

`intelligence/services/l3_evidence.py` 两处：按 `triage_level` 丢弃 P2/P3（fail-open：没这字段的源一律保留）；合法 JSON 空集不再落到纯文本兜底、把 `[` 造成假证据标题。判据在解析层，不进命令模板。

## 验证

- 英维克 cninfo 90 天：修前 4 条 P2 噪声 → 修后 0 条 + 空集措辞。
- 不误杀：双良节能 cninfo 90 天 21 条（1 P0 中标 + 16 P2 + 4 P3），过滤后恰好留那条 P0。
- `test_l3_evidence.py` 含空集不造假证据、无 triage_level fail-open、变异测试（只改 level 产出必须不同）。CI 绿。

## 遗留

- 互动易没有 `triage_level`，走 fail-open，未实测。
- 过滤后对答案质量的净影响没做 A/B。
- 合并后 l3 证据消费率分母会变（噪声退出）。8792 未切，生产尚未生效。
