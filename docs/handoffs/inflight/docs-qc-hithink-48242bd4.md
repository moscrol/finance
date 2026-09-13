# hithink 十二轮独立 QC：数据通过，门禁两项 P1 退修

## 这个分支做什么
审 `48242bd4` 的 v3 门禁与证据绑定；只增加审查文档、JSON 与诊断探针，不改候选业务代码。

## 决策与被否方案
- 数据与门禁分别裁定：正常重放支持旧结果，真实 Git 故障证明门禁仍可误放行；否了「22 项绿即全通过」与「旧收据全作废」。
- 只审不修；交实现方补门禁及故障回归。详见 `docs/handoffs/2026-09-13-hithink-48242bd4-qc.md`。

## 当前状态
审查材料随本提交入仓；候选及施工树未改，未合 main、未换生产库。两项 P1：
1. `scripts/reconcile_hithink_gate.py:125-126` 忽略 Git status rc，失败空 stdout 被判 clean。真实损坏临时索引 + dirty marker 完整跑出 22/22 PASS、exit 0。
2. `:94-96` 报告 fallback 仍写失败 OUT_BASE。路径与普通文件重名时只有 traceback、exit 1，无结构化 FAIL。

## 已验证
- 独立干净 48242bd4 四组测试 77p / 9.28s，门禁 Ruff 通过；收据 `20260913T153323Z-48242bd4.json`。
- 提交 gate/child 报告等于原 run；脚本/parquet/before 哈希相符；22 项；16 payload 仅 lessons 合并冲突保留双方。
- 历史 before+parquet 正常重放 22/22 PASS、exit 0；真实 Git 错误重放也发绿。均不打开生产库。
- 小证据入 `docs/handoffs/evidence/20260913-hithink-48242bd4-qc/`；原件在 `~/.finance-runtime/reviews/hithink-48242bd4-qc/`。
- `scripts/review_hithink_gate_faults.py` 轻量模式在独立 probe-target 实跑，Ruff 通过；不是放行门禁。

## 未验证 / 已知边界
未重跑全量/前端/E2E/registry；9608p 是原 044d1661 收据。本轮正常重放源是历史 before，不代表当前生产新鲜度。未逐一注入超时/JSON 损坏等全部故障。

## 下一步
Git helper 非零 rc 立即结构化 FAIL；报告写入加独立仓外 fallback + 最终 JSON 输出。补真实坏索引、输出路径冲突/不可写等回归，在新干净 revision 重放并提交收据。合并与生产换库仍分别需授权。

## 踩过的坑
命令失败的空输出不是“没有违规”；报告兜底不能依赖原失败介质。最初 mock 探针对异常 repr 含路径的假定错误，已修重跑；最终误放行由真实 Git 完整重放证明。
