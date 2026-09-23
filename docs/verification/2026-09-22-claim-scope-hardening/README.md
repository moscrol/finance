# 口径越界 lint 的三条 fail-open 闭合（2026-09-22）

审查 #850 时用真实首跑语料压出四条失效形状，其中三条是真缺陷、一条被实测推翻。
本目录是修复这三条的证据。基线 commit `1cf35f516`（#850 的 tip），本分支
`fix/claim-scope-hardening-0922`。

## 断言 → 证据

| # | 断言 | 证据 | 复跑命令 |
|---|---|---|---|
| 1 | P1/P3/P4 三条失效形状均已闭合，用的是真实首跑原文与原 episode 的最小改写 | `evidence/probe-closure.json` | 见下「探针复跑」 |
| 2 | 硬化没有改变两个冻结 run 的判定：规则命中与条数逐字段一致，退出码仍为 1 | `evidence/frozen-run-parity.json` | `python scripts/check_answer_claims.py <frozen-run> [--scope-total 20]` |
| 3 | 收紧限定词绑定后，仓内 6 份已归档答案 297 句重校准命中 0，未制造新误报 | `evidence/recalibration.json` | 见下「重校准」 |
| 4 | 定向回归 50 条通过（原 31 + 新 19），收据落在本分支 tip | `evidence/test-receipt-targeted.json` | `pytest intelligence/tests/test_answer_claim_scope.py tests/test_check_answer_claims.py -q` |
| 5 | 改动文件过全部 11 道 pre-commit 门 | `evidence/gates.json` | `pre-commit run --files <4 个改动文件>` |

## 三条修的是什么

1. **限定词绑定到断言**。原先整句任意位置出现「数据截至」「快照」就整句放行，于是
   `**数据截至 2026-09-18（最近一个已收盘交易日）**`——越界断言一字未改——直接静默。
   更糟：模块原先给出的 remedy 正把写手往这种写法引导，等于**教人把红灯写成绿灯**。
   现在要求范围限定词出现在断言短语前 12 字内，且一句里每次断言都要被限住。
2. **证据判定按注册表**。资金流证据改认 `finance_query` 注册的方向指标
   （`FUND_FLOW_METRICS`，6 个，`RegistryFactTests` 锁定注册表漂移），不再对整份
   payload 做子串匹配——原先 kb_search 的检索词里写「交易日历」就能让日期规则静默。
   相关事实：`finance_query` **没有**任何交易日历 dataset（日历只在
   `market_feature_store/trading_days.py`，agent 工具面够不着），所以
   `calendar_evidence` 只能由 `--calendar-evidence-source` 人工声明来源，不从 episode 猜。
3. **判据不可靠必须喊**。`--scope-total` 给了、但 episode 里解析不出比较范围数时，
   收据标 `degraded` 且**退 2**，不再悄悄退 0。取数形状一变就静默变绿，是把判据本身
   变成了摆设。

## 一条被推翻的审查判断

审查时我把「免责句在页脚、规则仍报」记成误报，要求改成篇级判定。动手前实测三种形状：

- 正文仍写「资金集中流入」+ 页脚免责 → 仍报。**报得对**：正文的越界断言还在，与免责自相矛盾。
- 正文只说成交活跃度 + 页脚免责（真正的合规写法）→ 不命中。**误报不存在**。
- 断言后紧跟撤回 → 仍报，同上。

结论：句级免责判定本身是对的，P2 撤回，不改。三种形状都钉成回归（`FundFlowDisclaimerShapeTests`），
防止后人当误报「修」掉。这条记在这里，是因为**审查方的探针同样要被真实语料压**。

## 探针复跑

```bash
python - <<'PY'   # 见 evidence/probe-closure.json 的 probes[] 字段
# P1: 把首跑原文的「数据日期：」换成「数据截至」，断言不动 → 应仍报 R1
# P3: 从 episode 摘掉 filters[].field=sector_code → 应 degraded 且退 2
# P4: 把某工具参数换成 {"query": "交易日历安排"} → calendar_evidence 应为 false
PY
```

## 重校准

```bash
git ls-files | grep -E '(answer\.md|golden_answers/.*\.md)$'   # 6 份，全量非抽样
# 对每份用空证据上下文跑 review_answer_claims，累计命中数
```

## 边界

- 四条规则仍是**关键词检出器**：换个说法就能绕过，干净不代表内容正确。本次只闭合了
  三条**已知**的绕过路径，不是覆盖率证明。
- 6 份语料 / 297 句不是统计样本，命中 0 不等于误报率 0。
- 两个冻结 run 是同一天两题，判定一致只说明本次收紧没动到这两题的结论。
- 本分支未跑全量测试；`answer_claim_scope` 仍无任何生产路径 import，合流门在合并后
  main tip 的批次门禁。
- `--scope-total` 的比较范围数目前只认 `filters[].field ∈ {sector_code, sector_ts_code,
  sector_name}`；别的取数形状会走 degraded 退 2，**这是有意的**——宁可报错也不冒充干净。
