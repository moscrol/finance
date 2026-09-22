# feat/adaptive-research-loop 在途

## 这个分支做什么

修研究回路取证、窗口收益计算与公开保真；收益与提示边界已修，收口卡在传输层不守绝对截止。

## 决策与被否方案

local_only 四只读能力、根 T900/单发帽75/共享窗150 不变，不开 derived_calculation。
`finance_query` 受限提供已观测日逐日复利摘要；不用文本算术解析器，不把 `river_query` 个股口径冒充板块。
收口审计在隔离树 `~/fwp-wt-adaptive-research-closeout-0922`（钉 `a9ba35159`）跑；否了本树直接跑、否了 stash——本树 19 路径未提交，混进去的绿说不清是哪份代码的。
本轮不跑真实模型：超时不受控时，失败分不清是内容差还是请求被拖断。
完整决策与收据见 `docs/handoffs/2026-09-22-adaptive-closeout-audit.md`。

## 当前状态

已提交部分裁决 **CHANGES_REQUIRED，不予收口**。未 push/PR/合 main/部署，未碰生产 8792。
本树 19 路径未提交（含新文件 `llm_http_transport.py`，上一轮在做的绝对截止传输层）——**非本轮产物，任何收据都不含它**，别当已验过的东西用。

## 已验证

隔离树 `a9ba35159`：ruff、registry 四项、ledger-crosswalk 全 exit 0；前端六步 exit 0（单测 110，E2E 34 passed/2 skipped）；完整 pytest **12840 passed / 85 skipped / 2 xfailed，exit 0**。两个自写收益对抗探针均过。收据根 `~/.finance-runtime/adaptive-closeout-20260922/`，裁决书 `VERDICT.md`。

## 未验证 / 已知边界

严格探针 `--assert-deadline` **exit 1，13 场景 7 个越窗**：`llm_refine.py` 1130/1178/1364/1474 行把获批秒数交给 `urlopen(timeout=)`，那只是 socket 空闲上限；1365 行起的流式读循环无绝对截止，持续滴流可无限延长。最狠的 `judge_late_report`：批 0.8 秒、2.94 秒才回包，却记 `success` 被采纳。
全绿不矛盾：`test_llm_timeout_diagnostic.py` 只断言探针自身，全仓没一条测试约束 `llm_refine` 墙钟——工具入库了，约束没入库。
独立审查**未完成**（新上下文 codex、只读沙箱、268 秒额度耗尽中断），不算外审，两位终审仍未满足。真实模型改稿复核未做，`adaptive-absence-live` 记的内容未过依然成立。

## 下一步

1 传输层落绝对截止（流式读循环内按单调时钟判，超时断连并归因，不靠对端配合）；2 补会红的回归测试进常规 pytest，`--assert-deadline` 那 7 条是现成用例；3 判官迟到回包判不可用、修预算归因；4 顺序不可颠倒：修完→重跑严格探针→真实改稿复核→两位终审。

## 踩过的坑

pytest 用主树 `.venv-workbench/bin/python` 并建独占 basetemp；里面密封 fixture 是只读的，清理前先 `chmod -R u+w`，一轮占 3.2G。
`timeout_asked` 不是实际耗时，核验轮数/实际调用数/零秒拒发要分账。
新增诊断工具时同时问"测出的东西有没有常规测试在守"，否则只在有人想起来跑时才起作用。
