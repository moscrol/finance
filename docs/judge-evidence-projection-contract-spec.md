# Spec：判官证据投影契约修复

> 修 `_semantic_evidence_projection()` 的两处契约缺陷 + repair 的删格下限。
> 依据：`~/.finance-runtime/live-probe-traceability/20260820-c6af3ec2-knevo-batch/` 五题 live + 生产函数离线重放。
> 2026-08-20 评审修订：A3/B1 夹具改用写手编号、C3 补第四分支、第 7 例改测第一发判官 report、C4 哨兵与解释变量拆开、§9 用 `R-20260820-*` 入账（不得误关 08-15 的 F-001/F-002/F-003）。

## 0. 基线与分支（先读，别写错树）

| 项 | 值 |
|---|---|
| 产出这批 run 的 revision | `c6af3ec2`（`gitea/main` 的祖先） |
| 本 spec 全部行号基于 | `gitea/main` @ `5d7529e5` |
| 实施分支 | `fix/judge-evidence-projection-contract`，**从 `gitea/main` 新建 worktree** |
| 当前检出树 | `feat/reading-rules-baseline-batch1` —— `c6af3ec2` **不是**它的祖先，`episode_semantic_verifier.py` 在此树为 3038 行、`gitea/main` 为 3734 行，**落后约 700 行。不要在当前脏树改 verifier。** |

当前主检出树长期脏。禁止 `git checkout -b`（会把无关改动带进新分支或直接失败）。用独立 worktree：

```bash
git fetch gitea
git worktree add -b fix/judge-evidence-projection-contract \
  /Users/a77/fwp-wt-judge-projection gitea/main
```

本 spec 若只存在于脏树工作区，拷进新 worktree 再改代码。venv 没有 `.pth`：新树直接用主树 `.venv-workbench/bin/python`。

## 1. 问题陈述

判官（semantic verifier）收到的证据注册表，不是写手写答案时依据的那批证据。两处失真，一处放大器：

| ID | 缺陷 | 位置（gitea/main） | 实测影响 |
|---|---|---|---|
| **D1** | 投影只送 `detail`，`title` 仅在 `detail` 为空时兜底 → 正文在 `title` 的工具（`news_search` / `graph_lookup`）退化成「时间戳+媒体名」「层级标签」 | `episode_semantic_verifier.py:3338` | 四题 payload 均无 `title` 键。B4 的 E31 只剩 `'2026-07-22 18:13:19 界面新闻'`（原 title 含「许继电气…12.45亿元」） |
| **D2** | 投影在 **bound 子集**上重新密排 E 编号，而写手用的是 `evidence_ordinal_table()` 在**全表**上发的编号 → 两套编号 | `episode_semantic_verifier.py:3333` | 未绑定条数：B4=0、B3=7、B1=8、A3=9。密排后判官 E4=写手 E9=07-13(-2.84)；写手 E4=07-20(+10%) **未绑定**。B3 草稿引 E37，密排表只到 E30 |
| **D3** | repair 无「删完还剩不剩必需输出」的下限 | `770/849`、`912/931`、`1039/1056`、**`1151/1162`（terminal，漏了会在最深删格路径失效）** | B4：判官拒 10 句 → 三格全 `missing`。849 行处 `structural` 已被赋成修复后草稿，原文在 `before_repair` |

**判官和写手都没错。** 判官「注册表无公司名与金额」按它的入参句句为真；写手的 E 编号在原始空间逐条对得上。错的是中间那段投影。

D1 的引入提交是 `344ab446 fix: bound semantic judge latency`——一次降延迟改动顺手收窄了数据契约，并被测试锁死（见 §5.1）。

A3 是**混合病例**：编号碰撞（D2）与「写手引用了未绑定日线」（E3/E4/E5 未进 binding）叠在一起。C2 只修前者——修好后 07-20 **仍不进** registry。夹具不得写成「投影后 E4=07-20」。

## 2. 要建立的不变式

1. **INV-1（内容完整）**：判官 payload 中每条证据，若源卡 `title` 非空则 payload 必含该 `title`；`detail` 同理。判官不得对「它没收到的字段」做存在性否证。
2. **INV-2（编号单一真本源）**：E 编号只由 `episode_protocol.evidence_ordinal_table()` 发放。任何消费者只能**引用**，不得**重发**。判官 registry 的 `evidence_id` 必须与同一 episode 内模型看到的 `evidence_id` 逐条相同。未绑定卡仍不送判官。
3. **INV-3（repair 下限）**：repair 不得使全部 evidence-grounded required output 同时 `missing`。触发时保留**该次 repair 之前**的 draft，不落 `marker_loss`。LLM 判官路径声明「判官结果可疑」；preflight 路径只用「repair 全灭」码，不把确定性闸门写成判官可疑。
4. **INV-4（失真可观测）**：投影一旦丢字段或编号错位，必须留下**能在回归时变亮**的计数字段；不允许静默。未绑定条数是解释变量，不是 D2 哨兵。

## 3. 变更清单

### C1 — `title` 入 payload（对应 D1，修 INV-1）

`intelligence/services/episode_semantic_verifier.py`，`_semantic_evidence_projection()`（3318 起）：

```python
# 3338 现状
            "detail": item.detail or item.title,

# 改为（两字段各自独立，空值省略）
            "detail": item.detail,
```
并在 `evidence_id` 之后、`detail` 之前插入：
```python
        if item.title:
            projected["title"] = item.title[:MAX_EVIDENCE_TITLE_CHARS]
```
- `MAX_EVIDENCE_TITLE_CHARS = 120`，从 `intelligence.services.tool_result_budget` 导入，**不要另写一个数字**（模型侧已用同一上限，两侧同源才能保证判官看到的和模型看到的是同一串）。
- `detail` 去掉 `or item.title` 兜底：`title` 现在有自己的槽位，兜底只会产生重复。若 `detail` 为空则省略该键（`compact_judge_payload` 本就会丢掉 `""`）。

**载荷增量与延迟**：最坏情况 36 卡 × 120 字 ≈ +4.3KB。实测 B4 判官 `remaining_seconds_at_entry = 255.79`、`timeout_asked = 50.0`、`attempt = 0` 完成——窗口有富余，`344ab446` 那次压缩的目标已由别的手段（判官窗治理）达成。**实施时仍须复核**：改后跑 §6 的离线重放，记录 payload 字节数与判官耗时，写进收据。

**替代方案对比（为什么不选）**：

| 方案 | 做法 | 否决理由 |
|---|---|---|
| 合并进一个字段 | `"detail": f"{title}｜{detail}"` | 丢字段边界；更要紧的是它能**绕过** §5.1 那条坏断言（`'"title"' not in serialized` 仍为真），坏测试保持绿灯——正是本次要修的失败形状 |
| 统一生产者语义 | 改 `_news_search` / `_graph_lookup` 让正文都进 `detail` | 爆炸半径大（多个工具 + 主链 observation 文案 + 既有夹具），且 `title` 本就是「标题」的正确归属。列为 §8 后续项 |
| 只对 news/graph 特判 | 按 `item.tool` 决定是否带 title | 白名单必漂：下一个把正文放 title 的工具接进来时静默复发。**认不出来就 fail closed** 的反面 |

### C2 — E 编号复用既有真本源（对应 D2，修 INV-2）

`gitea/main` **已经有**这个真本源，判官是唯一一处自己另编的地方：

| 设施 | 位置 | 谁在用 |
|---|---|---|
| `evidence_ordinal_table(evidence) -> {content_hash: "E<n>"}` | `episode_protocol.py:419` | `agent_episode.py:439`（主链 `tool_result` 事件）与 `agent_episode.py:1981`（只读分支路径），两处都已复用 |
| `resolve_evidence_refs()` | `episode_protocol.py:440` | 把模型写的 `E1..En` 反解成 `content_hash` 存进 binding |
| `strip_hashes_for_model()` | `episode_protocol.py:492` | 模型上下文**刻意只留 `E1..En`、剥掉 hash**（注释：誊抄 16-hex 是 B1/B7 零绑定的根因） |

改法：

```python
def _semantic_evidence_projection(outcome):
    ordinals = evidence_ordinal_table(outcome.evidence)   # 新增：唯一发放点
    bound_hashes = {...}                                   # 不变
    alias_by_hash: dict[str, str] = {}
    registry = []
    for item in outcome.evidence:
        if not item.content_hash or item.content_hash not in bound_hashes:
            continue
        evidence_id = ordinals[item.content_hash]          # 3333 改：不再 f"E{len(registry)+1}"
        ...
```

- `alias_by_hash` 用同一张表填，`output_bindings.evidence_ids` 自动跟着对齐。
- **registry 变稀疏**（`E1, E4, E5, E9, …`）是**正确结果，不是缺陷**。判官 system prompt 那句「`evidence_registry` 使用本次裁判内的 E 编号，`output_bindings.evidence_ids` 与其对应」需同步改成「E 编号与正文引用同一空间，可不连续」——否则 prompt 里那句声明仍与实际不符（这正是 D2 的 `violated_authority: system`）。
- `ordinals[...]` 缺键理论上不可能（bound hash 必来自 evidence），但仍要 `KeyError` 硬失败，**不要 `.get()` 兜个默认值**——兜底会把「表对不上」变成静默错编号，退回原缺陷。

**替代方案对比**：

| 方案 | 否决理由 |
|---|---|
| 把未绑定证据也送给判官，让编号自然连续 | 破坏 `"only answer-bound evidence"` 这个有意的设计——判官会拿未绑定卡去支持句子，等于放宽绑定纪律 |
| payload 里加 `raw_index` 字段让判官自己映射 | 两套空间仍然并存，只是把映射负担推给 LLM（间接寻址是模型弱项）。留两套空间就必然继续漂 |
| 反过来改写正文里的引用编号去迁就压缩表 | 需要 mutate 用户可见文本，属 repair 类操作，风险高于收益 |

### C3 — repair 删格下限（对应 D3，修 INV-3）

**四处** marker-loss 调用共用一个 helper（`770/849` preflight、`912/931` 第一发后、`1039/1056` 第二发后、`1151/1162` terminal）。漏掉 terminal，闸门会在最深删格路径上失效。

```python
def _repair_wiped_all_required(contract, marker_loss: tuple[str, ...]) -> bool:
    """repair 是否把全部 evidence-grounded 必需输出都删没了。"""
    required = {
        str(item.output_id)
        for item in getattr(contract, "required_outputs", ())
        if getattr(item, "required", True)
        and str(getattr(item, "grounding_mode", "evidence")) == "evidence"
    }
    return bool(required) and required <= set(marker_loss)
```

命中时**不走** `_marker_loss_partial_public()`，改为：

- `status="partial"`
- `public_answer` = **该次 repair 之前**的 draft（849 行必须用 `before_repair`，不是赋值后的 `structural.outcome`；912 用当时的 `structural`；1039 用 `repaired_verified`；1162 用 `twice_verified`）
- `gap_output_ids=()`
- `repair_withheld=True`（落进 `to_dict()`）。`JudgeStatus` 不扩枚举：现网 B4 已经是 `judge_status=repaired`（删格后）。闸门拦截后仍用 `repaired`，靠 `repair_withheld` + 新 issue 码与「真的修过」区分。
- issues 追加：
  - LLM 判官路径：`code=repair_wiped_all_outputs :: semantic repair removed every required output; judge verdict treated as suspect`
  - preflight 路径（770/849）：`code=preflight_wiped_all_outputs :: preflight repair removed every required output`——**不要**写成判官可疑。那是数字/星期/路径闸门，不是 LLM。

理由：三格同灭时，「判官全对而答案该是空的」与「判官入参坏了」不可区分；此时保留已核验事实 + 显式声明可疑，比交一个空洞答案对用户更有用。

**刻意不做**：不加「拒绝率超过 X% 即视为可疑」的阈值闸门。阈值需要校准数据（多少比例算异常），我们只有 5 个样本；无数据的阈值是**发明触发条件**，正是判官该拒的那类东西。全灭判据是确定性的、无参数的，先上这个。密度阈值列入 §8，等 §6 重放攒够样本再谈。

### C4 — 失真计数（修 INV-4）

`semantic_verifier` 落盘块（`SemanticEpisodeOutcome.to_dict()`）新增字段。`_semantic_evidence_projection` 顺带返回计数。

| 字段 | 含义 | 角色 |
|---|---|---|
| `projection_dropped_field_chars` | **整字段丢掉**的 `title`/`detail` 字符数（截断不计） | D1 回归哨兵；修好后恒为 0。`> 0` 告警 |
| `projection_truncated_field_chars` | 按 `MAX_EVIDENCE_TITLE_CHARS` 截掉的字符数 | 解释变量，长 title 会 > 0，不算回归 |
| `projection_ordinal_mismatch_count` | bound 的 issued id 集合与 emitted id 集合的对称差（不是「密排 vs 写手」逐条对比——修好后 A3 仍会有未绑定条，那种对比会假红） | **D2 回归哨兵**；修好后恒为 0。有人改回 `f"E{len(registry)+1}"` 就会亮 |
| `evidence_alias_offset` | `len(outcome.evidence) - len(registry)`（未绑定条数） | 解释变量。A3=9、B1=8、B3=7、B4=0 在修好后仍成立，**不能当 D2 哨兵** |

三个数 + 一个解释变量，不是日志洪水。

## 4. 不在本次范围（明确写下，免得下一个 agent 以为漏了）

- **不改生产者**（`agent_research._news_search` 的 `detail=f"{item.date} {item.source}"`、`_graph_lookup` 的 `title=company`）。C1 之后它们无需改动。
- **不改判官模型/供应商/窗口**。超时已修（五题 `asked=50, attempt=0, exc=None`），本 spec 不碰预算。
- **不处理 A3 库内 07-21 = 07-20 完全同值**（克隆脏数据，独立问题）。
- **不把 A3 未绑定的 07-20 日线补进判官 registry**（那是写手 binding 缺口，不是投影契约）。
- **不处理 B4 未调用 `market_data`**（`missing_mandatory_capability`，独立缺陷）。
- **不处理 `answer_marker_coverage` 与 verifier 的口径冲突**——并入账本 `R-20260815-03` 的样本，不在此结案。**禁止**把 08-15 那条 F-003 标 refuted。
- **不处理 B3 他题材热度错绑**（报告 R-3 / F-003）。只登记 `R-20260820-03` pending。

## 5. 测试计划（严格 test-first；竖切，不是一次性写完全部测试再实现）

缝（已由本 spec 钉死，实施时不再另确认）：

1. `_semantic_evidence_projection` 的公开返回值（判官 JSON registry / bindings）
2. `SemanticEpisodeVerifier.verify` 在「repair 会清空全部 evidence-grounded required output」时的公开结果
3. `SemanticEpisodeOutcome.to_dict()` 上的失真计数字段

### 5.1 先改坏测试（否则正确修复会被判成回归）

`intelligence/tests/test_episode_semantic_verifier.py:669`：

```python
assert '"title"' not in serialized      # ← 把缺陷写成了预期行为
```

`title` 被和 `source` / hash 一同当成「内部标识」排除，但它是**内容**。改为：

```python
assert '"title"' in serialized          # 内容字段必须在
assert '"source"' not in serialized     # URL 仍不外送
assert '"internal_locator"' not in serialized
assert '"content_hash"' not in serialized
```

同时 `648`/`654` 两处精确 dict 断言要跟着更新。

**夹具本身也必须换**——这是关键，不换则两个缺陷都照不出来：

| 现夹具 | 为什么照不出缺陷 | 换成 |
|---|---|---|
| `market_data` 卡，`detail="市场成交额与结构观察"` | 正文恰好在 `detail`，D1 不显影 | 至少一张 `news_search` 形卡：`title="许继电气：中标…约12.45亿元"`、`detail="2026-07-22 18:13:19 界面新闻"` |
| 1 条 bound 证据且在 index 0，另 1 条 unbound 在其后 | `f"E{len(registry)+1}"` 恰好等于 raw index，D2 不显影 | ≥2 条 unbound **排在 bound 之前**，使密排 id ≠ 写手 id |

### 5.2 新增不变式测试

| 测试 | 断言 | 覆盖 |
|---|---|---|
| `test_projection_carries_title_when_body_lives_in_title` | payload 中该卡 `title` 含「许继电气」与「12.45」 | INV-1 |
| `test_projection_reuses_episode_evidence_ordinals` | `{r["evidence_id"] for r in registry} == {evidence_ordinal_table(ev)[h] for h in bound}`，且未绑定证据在前时 registry 首项 id ≠ `E1` | INV-2 |
| `test_projection_ids_match_model_facing_ids` | 同一 evidence 元组，`attach_evidence_ordinals()` 与投影给出的 id 逐条相同 | INV-2（跨模块对账，最有价值的一条） |
| `test_repair_refuses_to_wipe_every_required_output` | 注入拒 10/22 句的假判官 → 不产生「三格全 missing」，改出 `repair_wiped_all_outputs`，`repair_withheld is True` | INV-3 |
| `test_projection_reports_zero_dropped_chars` | `projection_dropped_field_chars == 0` 且 `projection_ordinal_mismatch_count == 0` | INV-4 |

### 5.3 真实数据回归夹具

从四份 frozen run 抽**最小夹具**（只取 `outcome.evidence` + `outcome.bindings`，别把 300KB 的 `continuous-episode.json` 提交进仓），落 `intelligence/tests/fixtures/judge-projection/`。

编号一律用 **`evidence_ordinal_table`（写手空间）**，禁止用密排后的 E 号当预期——那会把缺陷锁成绿灯。

| 夹具 | 断言 |
|---|---|
| `b4-power-grid.json` | 投影后 **E31** 的 `title` 含「许继电气」「12.45」；`evidence_alias_offset == 0`；`projection_ordinal_mismatch_count == 0` |
| `a3-lixin-energy.json` | 投影后 **E9** 的 detail 含 `2026-07-13` 且 `-2.84`；**E4（07-20 +10%）不在 registry**（未绑定）；offset == 9 |
| `b1-photoresist.json` | 投影后 **E11** 含「容大感光」；密排曾把它叫做 E6，修好后不得再是 E6；offset == 8 |
| `b3-solid-state.json` | registry 最大 id == `E37`（**不是**密排的 `E30`）；offset == 7 |

内容均为公开行情与新闻标题，无凭证/PII，可入仓。

## 6. 验收判据（固定 8 例，逐条报，不报混合百分比）

| # | 案例 | 通过判据 |
|---|---|---|
| 1 | 5.1 改后的单测 | pass |
| 2 | `test_projection_carries_title_when_body_lives_in_title` | pass |
| 3 | `test_projection_reuses_episode_evidence_ordinals` | pass |
| 4 | `test_projection_ids_match_model_facing_ids` | pass |
| 5 | `test_repair_refuses_to_wipe_every_required_output` | pass |
| 6 | 四份真实夹具断言 | 4/4 pass |
| 7 | **离线重放 B4**（补 title + 对齐编号后重跑现役判官） | 见下 |
| 8 | 全量 `intelligence/tests/` | 不低于修前读数；payload 字节数与判官耗时记入收据 |

第 7 条是**唯一能证明「payload 是主因」的实验**，对应 triage 报告 **H5**（`INCONCLUSIVE`：空 `text` 是否充分导致误判）。报告里没有 H6。

**测量点（写错会得到假阴性）**：

- 必须读 **第一发判官** `GroundingJudgeReport.rejected_sentence_indexes`。
- 不得读最终 `SemanticEpisodeOutcome.rejected_claim_indexes`：B4 落盘该字段是 `[]`，10 句拒绝只活在 `issues` 文本里，随后被三格 `marker_loss` 盖掉。
- 不得用 `intelligence/eval/grounded_replay.py`：那是 Grounded Composer 链，不是 continuous episode 判官。
- 最小重放：冻 `outcome.evidence + bindings + draft` → `_semantic_evidence_projection` → `_judge_request` / `_run_judge` → 读 first report。

通过判据：`len(rejected_sentence_indexes)` 由 **10** 降至 **≤4**；句 **16/17/22** 从 issues 消失（这三句否证的内容都在 title 里：E36=「22交21直」，E31–E35=公司名与金额）。若没降到 ≤4，说明判官除入参外还有别的严苛来源，**此时不要继续堆 prompt，回去重新分诊**。

跑测试用 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。宿主 `python3` 缺依赖，会给出偏高且看起来完全合理的失败数（实测 71 vs 14）。

变异测试：改前先提交（`git checkout` 会丢未提交实现）；`.pyc` 缓存会让同长度改动在一秒内还原时伪造出「回归」——两条新测试各做一次变异验证。

## 7. 实施顺序

1. 建 worktree（§0）。拷 spec。
2. 竖切 C2：写 §5.2 编号两条 → 确认红 → 改投影用 `evidence_ordinal_table` → 绿。抽 §5.3 夹具（A3/B1/B3 编号断言）。
3. 竖切 C1：改 §5.1 坏断言 + title 测试 → 红 → title 入 payload + prompt 那句声明 → 绿。B4 夹具 title 断言。
4. 竖切 C3：wipe 测试 → 红 → 四处闸门 + `repair_withheld` → 绿。
5. 竖切 C4：计数断言 → 红 → 落盘字段 → 绿。
6. 第 7 例离线重放，出收据。无判官凭证则记 `not_run`，不把单测绿写成 H5 已结。
7. 回写（§9）。合 `main` 等用户确认，不强推。

## 8. 后续项（本次不做，登记以免丢）

- 统一各工具 `detail` 语义，或明确写下「`title` 是正文槽位之一」的契约（C1 的 §3 替代方案二）。
- repair 拒绝密度阈值闸门——等 §6 第 7 例攒够样本再定，不要凭空拍。
- 全树排查还有几处消费 `AgentEvidence` 时只读 `detail`（本次只查了判官投影与主链 observation 两处）。
- 复核 `344ab446` 那次压缩还排除了哪些字段（`source` / `freshness` 是否也有内容丢失）。
- A3 写手未绑定 E3/E4/E5（连板日线）——独立 binding 缺口。
- `R-20260820-05`：固态电池热度查询无题材过滤。

## 9. 回写

`gitea/main` 在写本 spec 时已经占用了 `R-20260820-01`（resume 结转稿）和 `R-20260820-02`（判官整窗 50s）。**不要复用这两个号。** 本单三条用 **`R-20260820-03/04/05`**。**禁止**把 08-15 Open 表里来源写作「标准 M1 分诊 F-001/F-002/F-003」的行标 refuted——那是另一份报告。

- `docs/prediction-ledger.md`：
  - `R-20260820-03` ← 报告 R-1 / F-001 现象，`DATA_CONTRACT_FIX`。验证=§6 第 7 例。本 PR 可 `confirmed`（第 7 例跑成才写；只绿单测则保持 pending 并注明契约≠实测）。
  - `R-20260820-04` ← 报告 R-2 / F-002 传播，`HARNESS_FIX`。验证=C3 单测 + B4 重放不再三格 missing。
  - `R-20260820-05` ← 报告 R-3 / F-003 热度错绑，`TOOL_DESCRIPTION_FIX`。**本次不实施**，只登记 `pending`。
  - F-001 的现象仍成立（判官否证了卡片已有字段），错的是 L0=`REASONING`。这是未入账发现的层判修正，**不是**已登记预测被证伪，不进 streak。
- `docs/trace-profile.md`：补三个字段陷阱——(a) 判官 registry 的 E 编号在修复前与 `evidence_ordinal_table` 不是同一空间，密排 E4 可以是写手 E9；(b) 判官 payload 无 `title` 时，据卡片 `title` 反驳判官 issue 会得出错误结论；(c) 落盘 `rejected_claim_indexes=[]` 不表示判官没拒句，repair 之后该字段会被清空。
- `~/harness-reference/BUILD.md` + `KIT.md`（不另建清单）——
  - **模式 6 实例**：同一个 id 只能有一个发放点。`evidence_ordinal_table` 已是真本源，判官自己另编一套就必然错位，且错位幅度等于被过滤掉的条数、无人报错。
  - **模式 8**（原候选 8，本单为第二独立实例后晋级）：压 payload 要按「是不是判定依据」分类，不按「像不像元数据」分类。`title` 被和 hash 归成一类删掉，判官从此对新闻类证据全盲，覆盖率类审计永远发现不了。
