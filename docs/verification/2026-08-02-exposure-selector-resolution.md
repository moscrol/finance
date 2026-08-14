# 暴露选择器意图分辨率 probe 解读（2026-08-02）

产物：`docs/verification/2026-08-02-exposure-selector-resolution.json`
（`artifact_sha256=2b01aee9…db297`，`code_revision=267d1997`，工作树 clean）

模块：`intelligence/eval/selector_resolution.py`。冻结一次「固态电池」候选池（86 家），
对四个预声明意图分别选 12 家，再用纯函数计算集合/排名差异。

---

## 0. 与计划的偏差

计划命令里的 provider 是 GLM（`FORESIGHT_BUILTIN_LLM_*` + `glm-5.2`）。实际用
**cockpit 本地代理的 `gpt-5.6-sol`**（走通用 `LLM_API_KEY` / `LLM_BASE_URL` /
`LLM_MODEL` 覆盖）。文件名按**实际日期**命名为 `2026-08-02-*`，不套用计划里的
`2026-08-01-*`——换了模型的 probe 是另一份 artifact，不该冒充原计划那次。

---

## 1. 结论：`discriminative`，但**要打折看**

`report.outcome = discriminative`，`unique_ordered_lists = 4`（四个意图产出四份
互不相同的有序名单），`union_size = 23`（池 86 → 并集 23），`hallucinated = 0`。

**但 46% 的选择不是 LLM 做的，是确定性回填：**

| 意图 | LLM 实选 | 回填 | 幻觉 | LLM 占比 |
|---|---:|---:|---:|---:|
| beneficiary（谁最受益） | 12 | 0 | 0 | **100%** |
| **expansion（谁在扩产）** | **1** | **11** | 0 | **8%** |
| margin_elasticity（利润弹性） | 5 | 7 | 0 | 42% |
| revenue_realization（收入兑现） | 8 | 4 | 0 | 67% |
| **合计** | 26 | 22 | 0 | **54%** |

> ⚠️ `expansion` 这一列几乎不是意图选择的结果：**12 家里 11 家来自确定性回填**，
> 即那份名单主要反映的是池子的默认排序，不是「谁在扩产」这个意图。

因此下面的配对差异必须这样读：`beneficiary × expansion` 的低重合
（Jaccard 0.263）**有相当部分来自「LLM 选出来的 12 家」和「回填排序的 12 家」之间
的差异**，而不是两个意图被真正分辨开。

## 2. 配对指标

| 左 | 右 | Jaccard | Top-3 变化 | RBO(p=0.9) |
|---|---|---:|---:|---:|
| beneficiary | expansion | 0.263 | 1 | 0.626 |
| beneficiary | margin_elasticity | 0.263 | 3 | 0.213 |
| beneficiary | revenue_realization | 0.600 | 2 | 0.728 |
| expansion | margin_elasticity | 0.500 | 3 | 0.335 |
| expansion | revenue_realization | 0.500 | 2 | 0.616 |
| margin_elasticity | revenue_realization | 0.500 | 3 | 0.307 |

*RBO = Rank-Biased Overlap，头部排名权重更高；越低表示头部差异越大。*

**最可信的一对是 `beneficiary × margin_elasticity`**：Jaccard 0.263、Top-3 全换、
RBO 0.213（六对里最低），且两边 LLM 占比分别是 100% 和 42%——头部确实换了人。
名单也符合直觉：受益方向选出材料/设备端（厦钨新能、三祥新材、天赐材料、纳科诺尔），
利润弹性方向选出电池厂（鹏辉能源、孚能科技、亿纬锂能、国轩高科），
**原材料降价时利润弹性最大的确实是电池厂而不是材料厂**。

`beneficiary × revenue_realization` 重合最高（0.600 / RBO 0.728），合理——
「谁最受益」和「谁先兑现收入」本来就高度相关。

## 3. 证据覆盖（只读，不进排序/prompt）

| 意图 | 选中中位数 | 池中位数 |
|---|---:|---:|
| beneficiary | 2.0 | 1.0 |
| expansion | 2.0 | 1.0 |
| margin_elasticity | 1.5 | 1.0 |
| revenue_realization | 1.0 | 1.0 |

选中公司的证据条数中位数 ≥ 池中位数，没有出现「选了一堆没证据的公司」。
该指标按设计只读，不参与排序也不进 prompt。

## 4. 判断

**意图分辨能力是存在的，但不稳定。** 最强的一对（受益 vs 利润弹性）分辨得干净
且符合产业直觉；最弱的一环是 `expansion`——LLM 基本没选出来，靠回填凑满。

「谁在扩产」需要的是**扩产公告/在建工程/产能规划**这类硬事实，而候选池的
`role` 字段主要是概念关联描述。**这更像是候选池缺该维度的事实，而不是选择器
不会选。**

### 建议

| 优先级 | 动作 |
|---|---|
| 高 | 给 `backfilled` 设阈值：单个意图回填占比 > 50% 时该意图应标 `unjudgeable`，不参与 `discriminative` 判定。否则回填会伪造出分辨率。 |
| 中 | `expansion` 类意图需要候选池带扩产类硬事实字段，否则这条维度问不出东西。 |
| 低 | 换回 GLM 复跑一次，确认结论不是模型特异的。 |

## 5. 复核

```bash
python3 -c "import json;d=json.load(open('docs/verification/2026-08-02-exposure-selector-resolution.json'));print(d['report']['outcome'], d['report']['telemetry_totals'])"
# 预期：discriminative {'llm_selected': 26, 'backfilled': 22, 'hallucinated': 0}
```
