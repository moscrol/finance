# 更正：evidence-bound output rate 是算得出来的，但它是阶跃函数

- 日期：2026-08-17 ｜ 更正对象：`docs/handoffs/2026-08-17-dispatch-f-addendum-2-stratify.md` §2、
  `2026-08-17-dispatch-f-addendum-3-decision.md` §0、spec §9.4 的 5a 改名理由
- 数据源：`~/.finance-runtime/evals/arm-a-cal-20260816/`（45 条臂级记录，Arm A，旧 pin）
- **不影响裁定结论**（5a 改名 + 主检验归位仍成立），但**改名的理由要换**。

## 1. 我错在哪

追加②§2 与追加③§0 都写：`source_ids` 0/254，所以 **evidence-bound output rate
「在这批产物里算不出来」**。

**错。找错字段了。**

§9.3 写的是 evidence-bound **output** rate ——**输出级**绑定
（`direct_assessment` / `chain_mapping` / `counterpoint` / `falsification_conditions`
这些槽有没有挂上 evidence hash），**不是 claim 级**。

输出级绑定**在产物里，位置是 `arm["diagnostics"]["bindings"]`**，
每条带 `output_id` / `evidence_hashes` / `basis` / `gap`。

```python
def ebo(a):
    b = [x for x in (a.get("diagnostics") or {}).get("bindings") or [] if isinstance(x, dict)]
    if not b:
        return None                      # 未定义，不是 0
    return sum(1 for x in b if x.get("evidence_hashes")) / len(b)
```

`claims[].source_ids` 全空这件事本身仍然属实（T-F 已查明是链路不是漏记），
但**那是 claim 级，本来就不是 §9.3 这个指标的载体**。

## 2. 真算出来之后：结论更硬，不是更软

| stop_reason | n | 均值 | **组内方差** |
|---|---|---|---|
| `numeric_lineage_gap` | 12 | **1.000** | **0.0000** |
| `model_finish` | 9 | **0.000** | **0.0000** |
| `repair_model_finish` | 1 | 0.000 | 0.0000 |
| 合计可算 | 22 | 0.545 | 0.2479（**全部是组间**） |

**bindings 为空、指标未定义的有 23/45**（全部 `repair_model_unavailable` 6、
`runner_exception` 5、`deterministic_fast_path` 5，以及诚实闸 19 条里的 7 条）。

按题看，**没有任何一道题存在组内方差**：

```
contextual-follow-up  1.000(v=0)   counterfactual-mainline  0.000(v=0)
current-mainline      1.000(v=0)   unfamiliar-methodology   0.000(v=0)
rebound-duration      1.000(v=0)
theme-comparison      1.000(v=0)
weekly-market-cause   1.000(v=0)
```

**这个指标在给定题目与终局桶之后是确定的——它是阶跃函数，不是带噪声的连续量。**
它那 0.2479 的「方差」百分之百来自「这次落进了哪个桶」，
不含任何「同一条件下质量高低」的信息。

## 3. 对已发裁定的影响

| 裁定 | 是否受影响 |
|---|---|
| 5a 改名 | **仍采纳，但理由换**：不是「算不出来」，而是**「算得出来，但它是阶跃函数、且半数运行未定义」** |
| 主检验归位到 Runtime 质量块 | **不受影响，反而更强**——阶跃函数不可能给通用层改动提供分辨力 |
| 领域侧降级为护栏 | **不受影响** |
| 不开 900 | **不受影响** |
| T-F 的 v=0.275 / 845 | 其代理（记录是否带 citations）与本口径的 12 条命中**完全重合**，是忠实代理；但两者都在量「落进哪个桶」 |

**新增一条给 §9.4 的要求**：报告该护栏时必须写明
**「未定义」那 23/45 怎么处理**（计 0 还是排除）——两种算法给出的数差很远，
不写清楚就是另一种假绿。

## 4. 顺带：Runtime 质量块的字段可用性（给 af）

同一批产物，45 条：

| §9.3 项 | 产物里 | 说明 |
|---|---|---|
| P50/P95 延迟 | ✅ `latency_seconds` 45/45 | 实测 P50=91.9s、P95=183.1s、均值 89.5s、标准差 64.0s |
| token 计量 | ⚠ `input_tokens` 29/45 | 16 条缺，需说明缺失机制 |
| provider 重试 | ✅ `provider_attempts` 45/45 | |
| 工具调用数 | ✅ `tool_calls` 45/45 | 只有计数，**没有 denied/invalid 细分** |
| 协议问题 | ✅ `protocol_issues` 25/45 非空 | |
| repair 恢复率 | ⚠ 可从 `stop_reason` 导出 | `repair_model_finish`=1 / `repair_model_unavailable`=6 |
| **cancel / resume / restart 成功率** | ❌ **无字段** | |
| **Trace / 事件对账完整率** | ❌ **无字段**（`diagnostics.events` 有事件，但无对账结果） | |
| **tool denied / invalid 率** | ❌ **无细分字段** | |
| **首轮超时率** | ❌ **无字段** | |

**延迟那项数据完整、是连续量、标准差 64.0s**——功效算得出来。
**打 ❌ 的四项在开窗前先确认要不要补记录**，否则会重演「跑完才发现没记」。
