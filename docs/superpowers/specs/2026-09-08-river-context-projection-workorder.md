# 工单 #34：上下文投影契约 `ContextProjection` + `projection_hash` 台账门禁（G-14）

> 日期：2026-09-08
> 上游：`2026-09-06-personal-research-calibration-endstate-design.md` **§4.5 上下文投影契约**（契约正文，本单照抄不改）、§4.2（判断轨归因字段：`agent_judgment / observation_script / scenario_tree` 必带 `model_id / framework_version / projection_hash`）、§10 最小验收集第 3、11 条、§11 第 11 条（投影门禁）；`2026-09-05-time-river-gap-roadmap.md` §2.5 G-14
> ⚠️ 上述 §3.3 / §4.4–4.6 / §10 第 9–14 条是 2026-09-06 第二轮审阅写入的，**截至 09-08 只在主检出的工作区里、从未提交**；本工单所在分支 `docs/closeout-workorders-0908` 已把这四个文件（含 `UBIQUITOUS_LANGUAGE.md` 与路线图 §2.5）一并带上，读工单前先确认你的树里有 §4.5
> 优先级：**P0（欠账在滚）**——路线图写「G-03 接进每日复盘之前必须先有它」，但 PR #606 已经把带读接进了每日复盘。今天起每一条从带读派生并登记的观察剧本，都没有「它当时看到了什么」的哈希；晚一天，就多一天的判断永远回放不出上下文
> 规模：中单（一到两天）
> 分支：`feat/river-context-projection`
> 依赖：G-02a 六轨读取面（已在 main）。**不依赖 G-01**——母本未成前全部 `selected_by=default`，管线先通
> 被依赖：#37 情景树（`realized_path` 与树对象都要带 `projection_hash`）；G-01 落地后授课框架规则作选择器接在这里
> 并行冲突：本单改 `guided_reading.py` / `observation_script.py` / `checkpoints.py`；#37 也要碰 `checkpoints.py`，**#37 排在本单合入之后**

---

## 0. 一句话

今天带读是「切片 → 直接渲染」，中间没有一层可哈希的「模型 / 读者看到的是什么」：渲染函数把 payload 键**字母序截到 6 个**、个股节点折成一行计数、轨按字母序排，这些选择既没有理由字段也没有记录。本单在切片与任何消费方之间插一层纯函数 `project(slice, rules) -> ContextProjection`：选了什么、按什么规则选、省略了什么、限制与缺口是什么，全部显式；对它做确定性哈希 `projection_hash`；台账对 agent 产物（`agent_judgment` / `observation_script`）**没有这个哈希就拒收**。

---

## 1. 现状 [实测 @ `gitea/main` `8e452e72`]

| 位置 | 现状 | 问题 |
|---|---|---|
| `intelligence/services/guided_reading.py:62` `_PAYLOAD_KEYS = 6`；`:131` `sorted(k for k in payload ...)[:_PAYLOAD_KEYS]` | 每个对象只渲染**字母序前 6 个**非空 payload 键 | 截断规则写死在渲染里，被丢掉的键不留痕；字母序不是任何领域顺序 |
| `guided_reading.py:147 _collapse_stock_nodes` | 个股级对象折叠成「N 条（标签×计数）」 | 折叠是对的（产品面不出名单），但「折叠了哪些 ref」没有落在任何可回放的结构里 |
| `guided_reading.py:191` / `:279` `for track in sorted(...)` | 轨按字母序 | 与 `river.TRACKS`（盘面→题材→舆论→资金→个股→判断，终局 §2 表序）不一致，且无 `selected_by` |
| `guided_reading.py:175 build()` | 纯函数，入参 `RiverSlice.to_dict()` 形状 | **好底子**：投影层插在它前面即可，不必改回放喂法 |
| `guided_reading.py:236 _draft_script` | 观察剧本骨架的 `evidence_refs` 直接从切片各轨对象的 `ref` 收 | 骨架带的是「所有 ref」而不是「投影里选中的 ref」，两者今天恰好相等，投影一上就会分叉 |
| `intelligence/services/observation_script.py:110 ObservationScript` | 有 `evidence_refs`、`framework_version`、`hindsight`、`knowledge_cutoff` | **没有** `projection_hash` |
| `intelligence/services/checkpoints.py:198 register_checkpoint` | `object_type ∈ OBJECT_TYPES = ("judgment","agent_judgment","observation_script")`（`:56`），非法即抛 | **没有** `projection_hash` 参数；agent 产物与用户判断在「要不要带上下文哈希」上无区别 |
| `intelligence/services/episode_projection.py` | `project_durable_events` —— 运行底座 P0 的 **durable 事件投影**（episode 事件 → workbench trace） | **同名不同物**。本单的是「河切片 → 读者上下文」投影。新模块必须另起名，见 §2.1 |
| `rg projection_hash intelligence/` | 0 命中 | 缺口成立 |

---

## 2. 要做什么（三刀，可分三个 PR 也可一个）

### 2.1 刀 1｜契约与纯函数：`intelligence/services/river_projection.py`

形状照 09-06 spec §4.5，字段名不改；这里只写实现约束：

```python
@dataclass(frozen=True)
class ProjectedBlock:
    track: str
    object_refs: tuple[tuple[str, str], ...]   # (ref, source_hash) 有序；值不进投影，按 ref 回读主数据
    hardness: str                              # 块内最高硬度
    derivation: str                            # deterministic | frozen_llm
    selected_by: str                           # "default" | "framework:<framework_version>:<rule_id>"
    rendered_text: str                         # 消费方渲染用；**不进哈希**

@dataclass(frozen=True)
class ContextProjection:
    projection_version: str                    # "cp-v0"
    framework_version: str | None              # G-01 未成前恒 None
    task: str                                  # "guided_reading" | "ask_synthesis" | "scenario_tree" …
    source_ref: dict                           # {as_of | start,end; entity_id; knowledge_cutoff; pit_grade; hindsight; alias_applied}
    blocks: tuple[ProjectedBlock, ...]         # 有序
    omitted: dict[str, int]                    # {track: count}；本单额外落 omitted_refs{track: [ref]} 供 replay 对账
    limits: tuple[str, ...]                    # 强制块
    gaps: tuple[str, ...]                      # 强制块
    budget: dict                               # {limit, used}
    label_version: str                         # methodology_backtest.labels.LABEL_VERSION
    def canonical_json(self) -> str            # sort_keys、ensure_ascii=False、无空白；rendered_text 剔除
    @property
    def projection_hash(self) -> str           # "cp:" + sha256(canonical_json)[:16]

def project(source: dict, *, framework_version: str | None, task: str, budget: int, rules: Sequence[SelectionRule] = ()) -> ContextProjection
```

规则（§4.5 六条硬规矩逐条落地）：

- **哈希 = hash(有序 blocks 的 refs + framework_version + projection_version + budget + source_ref)**（§4.5 原文），`rendered_text` 不在内；同一对象被重发布改了数值 → `source_hash` 变 → 哈希变；改渲染文案 → 不变。
- **默认序**（框架无规则时）：轨按 `river.TRACKS`；轨内 **硬度降序 → `recorded_at` 升序 → `ref` 字典序**（§4.5 原文，不是今天的字母序）；`frozen_llm` 对象排在同轨 `deterministic` 之后并在块上标 `derivation`；每块 `selected_by = "default"`。
- **`gaps` 与 `limits` 排在事实块之前**，永远进上下文，不受预算约束。
- **预算按块整体省略**：`budget` 是对象条数上限（v0 用条数，不用 token——token 数随模型 tokenizer 变，会让哈希跟着模型漂）；装不下的块整块进 `omitted`，**不得在对象中间截断**，也不再有「6 个键」这种键级截断——小白面要短，由消费方渲染时决定显示几个键，被省的键进 `rendered_text` 的「另有 M 项」提示，不影响哈希。
- `SelectionRule` 是协议：`(track, objects, budget_left) -> (selected_refs, omitted_refs, selected_by)`。本单只实现 `DefaultRule`（个股级对象折叠成计数块，其余全选）与测试用 `TopNRule`；**不写任何授课框架判读规则**——那是 G-01 之后的事。
- `omitted / limits / gaps / budget` 四块**必须存在**（空也要是空值），`canonical_json` 对缺任一块抛错。
- **不落库、不缓存**（终局 §9 / F4）：投影由 `(source_ref, framework_version, task, budget, projection_version, label_version)` 重算；哈希是回放钥匙，不是存储键。

### 2.2 刀 2｜`guided_reading` 改为投影的一个消费方

- `guided_reading.build(slice_dict, ...)` 内部先 `project(slice_dict, task="guided_reading", budget=…)`，`facts` 从 `ContextProjection.blocks` 渲染，`limits / gaps` 直接取投影的并**渲染在事实之前**（§4.5 第 2 条；今天 `render()` 的段序是 事实 → 限制 → 缺口，要换）；渲染仍可只显示前 N 键，但要加一行「本轨另有 M 项未显示（投影已含，hash=cp:…）」。
- `_draft_script` 的 `evidence_refs` 改取投影 `blocks[*].object_refs` 的 ref；`ObservationScript` 加字段 `projection_hash: str | None = None`（`make()` 透传；`_make_id` 不变——哈希不是身份）。
- `render()` 头部第二行加 `projection=cp:…`。
- **关掉带读时逐字节不变**：`run()` 关闭路径一行不动；`test_guided_reading_daily_seam.py` 里现有「关掉后逐字节不变」断言必须继续绿。开着的输出允许变（段序、哈希行）——那是新版本，不是回归。

### 2.3 刀 3｜台账门禁

- `checkpoints.register_checkpoint(..., projection_hash: str | None = None, model_id: str | None = None)`：记录里落两字段；**`object_type in {"agent_judgment", "observation_script"}` 且 `projection_hash` 为空 → `ValueError`（fail closed）**；`agent_judgment` 还要求 `model_id`（§4.2）；`judgment`（用户自己写的判断）两者可空，产品外补录的按 §4.2 在校准里单列（`calibrate` 出 `projection_hash_missing` 计数列）。
- 观察剧本登记路径（`observation_script.build_metric` / 复盘接线处）把 `script.projection_hash` 传进去；数据面派生的骨架 `model_id = "deterministic"`。
- `calibrate()` 的 `CategoryStat` 加一列 `with_projection_hash`（计数，不影响任何率）；存量无哈希的 agent 产物照旧计入，只是这列为 0——**不追溯拒收**。
- 新 CLI `scripts/river_projection.py replay --as-of D --entity E --cutoff C --task guided_reading --budget N [--framework-version V]`：重算投影、打印哈希；`--expect cp:…` 不等即非零退出。这是「每条 agent 判断都能回放它当时看到的上下文」的可执行形式。

---

## 3. 验收（逐条可打勾）

1. 同一 `(source, framework_version, task, budget)` 两次 `project()` 的 `projection_hash` 相等；路径上无 LLM、无盘外读（测试用夹具切片）。【09-06 §10 第 11 条前半】
2. 源切片里每个 `gap` 都出现在投影 `gaps` 里，且 `gaps / limits` 块在 `blocks` 之前渲染。【§10 第 11 条后半 + §4.5 第 2 条】
3. 改任一选中对象的 `source_hash` → 哈希变；改 `rendered_text` / 渲染文案 / 显示键数 → 哈希不变。
4. `omitted / limits / gaps / budget` 缺任一块 → `canonical_json` 抛错（测试）；预算 `limit=1` 时只省块不截对象（测试：任何 block 的 `object_refs` 要么整块在、要么整块在 `omitted`）。
5. 默认序：轨序 == `river.TRACKS`；同轨按 硬度降序 → `recorded_at` 升序 → `ref`；`frozen_llm` 排在 `deterministic` 之后；无规则时每块 `selected_by == "default"`。
6. `guided_reading.build` 输出里每条事实的 ref 都能在投影 `blocks` 里找到；观察剧本骨架 `evidence_refs ⊆ 投影 ref 集`。
7. 关闭带读（`FORESIGHT_GUIDED_READING=0` 与老用户默认关两条路径）每日复盘输出**逐字节**与 main 相同（既有 seam 测试续绿）。
8. `register_checkpoint(object_type="observation_script")` 不带 `projection_hash` → 抛错；`agent_judgment` 不带 `model_id` → 抛错；`judgment` 都不带 → 正常；错误信息里点名缺的字段。【§11 第 11 条】
9. `scripts/river_projection.py replay --expect` 对夹具切片命中 / 不命中各一例，退出码 0 / 1。
10. 真库冒烟（不进测试）：`as_of` 取最近一个交易日、实体「上证指数」，`replay` 两次哈希相等；把读数与哈希写进收据 `docs/verification/2026-09-08-river-context-projection.md`。
11. 干净树全量 `ruff 0` + pytest 红集不大于基线（基线看 `~/.finance-runtime/test-receipts/` 最近一份 main 收据）；`check_test_receipt.py --expect-revision HEAD`。

---

## 4. 非目标 / 红线

- ❌ 不写授课框架判读、不实现任何「框架规则选择器」的具体规则——那是 G-01 之后的事；本单只留协议与默认实现。
- ❌ 不新增存储、不缓存投影 JSON；调试要看全文用 `replay` 现算。
- ❌ 不改 `episode_projection.py`、不复用它的名字与类型；两种「投影」在文档里分别叫「**上下文投影**」与「**durable 事件投影**」，`UBIQUITOUS_LANGUAGE.md` 加这两条。
- ❌ 不追溯拒收存量无哈希记录；不改 `checkpoints._make_id` 的身份规则。
- ❌ 带读关闭路径一个字节不动。
- 个股级对象只进 `collapsed`，**不得**因为「投影要完整」就把个股名单放回渲染（`_collapse_stock_nodes` 的产品面边界不变）。

---

## 5. 教学注

- **为什么哈希 ref+source_hash 而不哈希渲染文本**：渲染文本会随文案、排版、显示条数变化，哈希它等于把 UI 版本钉进方法论台账；哈希「选了哪些对象、每个对象当时的内容指纹」才是「模型看到了什么」的稳定表述。这和 Git 的 tree object 一样——tree 哈希的是子项的 (mode, name, blob hash)，不是文件怎么在终端里显示。同一思路可用于任何「提示词上下文可审计」的系统：哈希检索结果 id 集，不哈希拼好的 prompt。
- **按块省略 vs 按键截断**：截断丢的是信息，省略丢的是「块」并留下收据（数量、原因、ref）。读者能问「省了什么」，回放能重建。替代方案是「不省略、全量渲染」——小白面上不可读；或「省略不记」——就是今天的样子。
- **fail closed 只对 agent 产物**：对用户判断强制哈希会把「用户随手记一句」变成必须先跑切片，产品面会死。分类型收紧是在「可审计」与「可用」之间的常规折中；同类做法见 Web 安全里对服务端产物强制签名、对用户输入只做校验。
- **替代方案对照**：(a) 直接把切片 JSON 全文存下来当上下文——违反终局 §9（第二套库）且体积随日增长；(b) 用 `as_of+cutoff` 当钥匙不算哈希——切片重发布后同钥匙不同内容，正是 #27（`recorded_at`）已经证明会发生的事。

---

## 6. 交接要求

- 在途交接 `docs/handoffs/inflight/feat-river-context-projection.md`（≤ 3K）；合入后 `UBIQUITOUS_LANGUAGE.md` 加「上下文投影 / durable 事件投影 / projection_hash / selected_by」四条。
- 路线图 `2026-09-05-time-river-gap-roadmap.md` G-14 条目回写「已落（#34）」；09-06 spec §10 第 11 条与 §11 第 11 条标「实测 ✅ @<sha>」。
- 台账地图 `docs/learning/ledger-map.md` 第 14 行（个人判断回检）备注 `projection_hash` 字段自本单起对 agent 产物必填。
