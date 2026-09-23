# 口径越界 lint · 2026-09-22 验收证据

把 2026-09-21 K3 首跑的四条实测反例做成确定性检出器（`intelligence/services/answer_claim_scope.py`）与离线判据（`scripts/check_answer_claims.py`）。

**这不是内容质量验收通过。** 检出器只认四种已知形状；干净不等于答案正确，命中也要人读原句。它换来的只有一件事：这四条再犯必被机器抓住，不必等人逐句读。结论见 [handoff](../../handoffs/2026-09-22-answer-claim-scope.md)。

| 断言 | 原件 |
|---|---|
| 材料题命中 1 条（`unit_gap_claim_contradicts_input`），退出码 1 | `evidence/claim-scope-run_20260921_183219_280474.json` |
| 行情题命中 3 条（日期／范围／资金流），退出码 1 | `evidence/claim-scope-run_20260921_183642_325351.json` |
| 仓内 6 份已归档答案、297 句、命中 0（空证据上下文，只有两条纯文本规则在跑） | `evidence/claim-scope-calibration.json` |
| 定向 31P，干净树 `ef9ff3b4` | `evidence/test-receipt-targeted.json` |
| 全量 12542P/85S/2X，Ruff 0 | `evidence/test-receipt-full-suite.json` |

全量收据的 `revision` 是基线 `a2c8d1f9` 且 `dirty=true`：跑的时候本次三个新文件还没提交，脏内容就是它们本身，提交后只补了定向复跑。**不要把这份全量当作 `ef9ff3b4` 的收据。**

调参过程中检出器自身被真实语料抓出三个缺陷，都已修并留回归：指标名「单位投资额／单位成本」被当成单位缺口（误报）、真正的缺口长句距动词 20 字接不住（漏报）、仓内 golden 快照里「不能视为最新交易日复盘」这句正确免责被判违规（误报）。

校准语料 6 份、297 句不是统计样本；空证据上下文下范围与单位两条规则本就沉默，命中 0 不能证明那些答案正确。归属全集个数由 `--scope-total` 显式传入（本次 20 来自当前主库 09-18 归属查询，非历史库重建）。

清单覆盖本目录全部文件（除清单自身），按 Git 内字节核验：

```bash
python3 scripts/check_evidence_archive.py docs/verification/2026-09-22-answer-claim-scope \
  --revision <本轮证据提交>
```

本轮无模型请求、无生产调用、无部署；检出器尚未接入 Episode 实时作答路径。
