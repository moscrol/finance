# D0 收据：周一原题复验 P0-C（2026-08-24）

- 规格：`docs/superpowers/specs/2026-08-24-harness-ceiling-and-8796-decouple-followup.md` §4
- 冻结题面：`2026-08-23-publication-and-contract-subtract-design.md` §5.1 / §5.2
- 台账：`R-20260824-10` → **confirmed**（三变量有绿结论；不是 Knevo A1）
- 生产：8792 `source_revision=8688545b9104` / `source_dirty=false` / `code_matches_repo=true`
- 探针：`scripts/workbench_probe.py --user probe-d0-p0c-monday-0824 --port 8792`
- 会话：`conv_cd80a52d1f9c41d4966f94e08e8f371d`
- run：`run_20260824_014139_633829`
- 工件：`~/.local/share/finance-workbench/users/probe-d0-p0c-monday-0824/runs/run_20260824_014139_633829/`
- 离线：同 SHA 树 `test_monday_tech_med_honors_dual_subject_and_stock_slot` + `test_ysjs_spoken_xia_is_not_part_of_subject` 2 passed（收据 `20260823T174120Z-9c4dfe91`）

结论：**D0 绿。** 可以进入 D1 / D3。禁止用本收据证 D3 已做。

---

## 判别变量（P0-C #1–#3）

| # | 锁什么 | 离线（`understand_query` @ 本树=8688545b+docs） | live 8792 信封 | 判 |
|---|---|---|---|---|
| 1 | 周一题 `subject` 同时有「科技」和「医药」，不得空串 | `subject='科技、医药'` | `task_frame.subject='科技、医药'`（`report.json` / `continuous-episode.json` 一致） | **绿** |
| 2 | `required_outputs` 含个股观察格（名单 + 代码 + 角色） | `company_mapping` 在 operators 与 required_outputs；description 为「股票名称 + 六位代码 + 角色（机会 / 出清或风险）」 | 信封 id=`company_mapping`；契约 description 同上；公开稿含六位代码（如 300308 / 300142 / 600276）且分「机会 / 风险」 | **绿** |
| 3 | 「分析下有色金属…」`subject` 不得以「下」开头 | `subject='有色金属'`，`startswith('下')` 为假 | 未另打 live（#3 是信封债，与 #1/#2 同一 `query_understanding`；8792 与离线同 SHA） | **绿** |

周一题其余信封（非本单红线，记一笔）：`question_type=general_finance_qa`（P0-C 允许）；`operators=('scenario_tree','company_mapping')`。

---

## live 观察（P0-C §5.1 live 条，不是离线红线）

| 观察 | 读数 |
|---|---|
| 公开 `answer.md` 含 `## 输出质检` | **无** |
| 研究 / 运输灯 | `research_status=complete` / `transport_status=completed` / `business_status=complete` |
| 判官 | `judge_status=repaired`；`gap_output_ids=[]`；结构 `verified_status=completed` |
| 个股段至少一只带六位代码 | **有**（多只） |
| 「质检降级」头 | **无**（与 Knevo A1 不同） |

正文有一句「8-21数据仅单日，证据不足，两假说并立」——这是情景树里假说并立的模型措辞，**不是** gap 路径「现有证据不足 / 未完成核验绑定」。P0-B 管的是后一条。本句不把 D0 打红。

判官 issue 一条：`numeric_unsupported`（无绑定的数值条件）。稿仍 `completed`/`repaired`，不是剥盘。不立案到 D0。

---

## Knevo A1 不是本单证据

题面：`2026-07-23 今天市场怎么样`（`~/.finance-runtime/four-arm-knevo-20260823/`）。

8792 臂公开稿头「【质检降级】部分必答格核验后不完整，残块保留」。信封是 `direct_assessment` / `supporting_evidence` / `risk_signals`，`subject=None`。语义 issue 含 `missing_mandatory_capability: market_data` + 发明阈值；`marker_loss` 列表空。

这是盘面题 + W1/V8 降级头，交给 D2 结案材料。**不得**写成 P0-C 漏网。

---

## 复算

```bash
# 离线信封
.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_query_understanding.py::test_monday_tech_med_honors_dual_subject_and_stock_slot \
  intelligence/tests/test_query_understanding.py::test_ysjs_spoken_xia_is_not_part_of_subject

# live 信封
.venv-workbench/bin/python -c "
import json
from pathlib import Path
p=Path.home()/'.local/share/finance-workbench/users/probe-d0-p0c-monday-0824/runs/run_20260824_014139_633829/report.json'
r=json.loads(p.read_text()); tf=r['task_frame']
print(tf['subject'], tf['required_outputs'])
"
```
