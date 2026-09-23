# #86/#87 部署帮助与晨汇消费候选

## 这个分支做什么
把 PR #846/#847 前向到当前 main，补齐部署 `--help` 无副作用与晨汇 source→label→teaching object→river 的离线验收。

## 决策与被否方案
- 完整校验七个 briefing label，NULL 与零严格区分；否了继续跳过 `briefing_hit_rps5_pct`，因为旧逻辑能让伪造零穿过值门。
- 逐行校验 label `computed_at` 不早于 source `recorded_at` 的日期；否了只看 object max 时间，因为早写行会被晚写行掩盖；日期源不支持同日盘中排序。
- K3 新会话无正式报告记 BLOCKED；否了把测试绿或中途事件当独立批准。
- KB #157 先于 finance #847 合入；两边只合一半最多只读 FAIL/BLOCKED，不会写行情/标签。展开 `docs/handoffs/2026-09-23-briefing-consumption-coupling.md`。

## 当前状态
业务修复已提交，随后只追加验证文档、QUEUE/INDEX 与交接；工作树当前 clean，未 push/合并/部署。用户确认前保持 WIP。#86 K3 精确绑定业务代码 head `6f14ed215184d5c97fae3c03513468c6c9ee9cd4`，限定离线 PASS（11 请求、无模型错误、报告与 verdict 齐全）；仅记录基线已有 P3 非原子 rsync 风险。#87 K3 仍为 INCOMPLETE（28 请求、1080s、无 REPORT/verdict），按 BLOCKED 处理。

## 已验证
- #86 定向：24 passed；#87 IMA + 晨汇：14 passed；最终可采信收据在 `/Users/a77/.finance-runtime/test-receipts/`，具体文件须用当前 HEAD 做 `check_test_receipt.py --expect-revision` 校验。
- `zsh -n`、Python ruff、`git diff --check`、`merge-tree` 通过。
- 真实 schema + `teaching_objects` + `slice_river` 合成探针：PASS；NULL/零 FAIL；早写 FAIL；日历不足 BLOCKED 且 labels DB SHA 不变。证据索引 `docs/verification/2026-09-23-briefing-k3-r2/README.md`。

## 未验证 / 已知边界
正式全量 Python gate 1200s 超时、无收据；frontend/e2e/registry 未在本 head 重跑。live 验收等 #61 补齐 `fact_market_daily`，本轮未造行情、未写 IMA。ordinary river 仅 `trade_date_only`；strict 仅教学日期过滤，非全历史冻结/全文 RAG。

## 下一步
用户确认后：合前刷新 main/KB PR 身份，按耦合顺序重跑可采信四叶；#61 就绪并单独授权后再跑 live。不要使用超时全量作为绿，也不要覆盖 KB 脏树。#86 安装调查未发现部署脚本副本，勿替换现有启动器或 LaunchAgent。

## 踩过的坑
pytest 收据必须看完整 revision；提交前 `070f6455` 的旧收据不能签本 head。ruff 不接受 shell 文件，shell 用 `zsh -n`。K3 `exit 143/deadline` 且无报告不等于 PASS。
