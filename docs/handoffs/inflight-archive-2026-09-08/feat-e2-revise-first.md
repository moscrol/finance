# feat/e2-revise-first

## 这个分支做什么
轨道 C / E2：会话口「修订版在前，审查意见进输出质检附录」。不换 `output_review` 6 项。

## 当前状态
HEAD `71b26df7`，树 `~/fwp-wt-e2-revise-first`。PR **#239**。live 过。**可合。未合 main，不切 8792。**

## 未验证 / 已知边界
- Engine B 回灌只跑了单测，live 走 Engine A。
- 本发判官 unavailable（R-06），附录内容是 transient issue，不是「弱证据硬写」。
- W3 同改 `conversation_orchestrator`，后合方 rebase。

## 下一步
1. 用户确认后合 #239（pathspec，勿 `git add -A`）。
2. 不要因可合就切 8792。轨道 D 等 C 合入。

## 踩过的坑
- 真研究题走 `_complete_continuous_turn`；只翻 ask 的 flag 验不到生产路径。
- `live_probe ask` 没有 `theme_track`。
- `_revise_synthesis_on_warn` 在 `stream_text_delta` 或 `review_gate is None` 时必须直接 return。
- sidecar health 看 `source_revision`，脏树 live 对不上 commit。

## 已验证
`:8815` @ `441c92da` dirty=false：陶瓷纤维跟踪题终稿正文在前、`## 输出质检` 在后。读数 `docs/verification/2026-08-19-e2-revise-first-live.md`。收据 `~/.finance-runtime/test-receipts/20260819T084606Z-441c92da.json`。
