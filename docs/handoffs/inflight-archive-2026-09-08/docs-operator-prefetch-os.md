# docs/operator-prefetch-os

## 这个分支做什么

把 2026-08-23 SPT×风远历史同构三臂的 PRIMARY 收成可施工设计：空 `manual` 不得覆盖已识别的 `history_analog`；Engine A 开场预取必须给**按 as_of 截断的** D10 或显式 gap。对照 Knevo：抄 OS/硬触发/单专项做法，不抄「只留 LLM 入口」。

**本分支只放文档。** 代码在另开的 `fix/operator-prefetch-os` 上做。

## 当前状态

树 `/Users/a77/fwp-wt-operator-prefetch-os` @ `docs/operator-prefetch-os` ← `gitea/main@90c069cb`。

- 设计：`docs/superpowers/specs/2026-08-23-operator-prefetch-os-design.md`（rev2）
- 计划：`docs/superpowers/plans/2026-08-23-operator-prefetch-os.md`（仅 P0，四个 Task）
- 未改任何生产代码，未切 8792。

三臂产物仍在 `~/.finance-runtime/trace-diff-spt-fengyuan-history-20260823/`。主仓脏树 `feat/reading-rules-baseline-batch1` 不要并进来。

## rev2 相对 rev1 改了什么（接手必读）

rev1 的 plan 有四个施工级缺口，rev2 已修：

1. **D10 有未来数据穿越，且是四处不是一处**（spec §4 事实 12）。`regime_block_for_llm` / `load_market_regime_artifact` / `load_market_regime_vectors` 三个签名都没有 `as_of`；base 查询无 `where`；「当前窗口」写死库尾；**z 标准化用全历史**（最隐蔽，修前两条也堵不住）；forward facts 会跨 as_of。修法是取数层一刀：`where trade_date <= as_of`。已升为 plan **Task 2，必须在接线前完成**。
2. **rev1 的 Task 2 骨架含两处 `# ... 保持原实现 ...`**，等于要求施工方凭空重打 60 行现役代码。rev2 改成**锚点式编辑**：新增一个 `_history_analog_items` 私有函数 + 在 `collect_prefetch_items` 里只替换 6 行，`market_forecast` / 发酵两段一字不动。
3. **rev1 的测试不能证伪**：只锁「缺库出 gap」，一个「永远返回 gap」的实现也能全绿。rev2 补正向用例（有数据必出 `[D10]`）与判别用例（两个不同 as_of 必须给出不同的块），并写进 spec §5.2 规则 7。
4. **D11 被漏掉**。冻结题面实测 `parse_stock_analog_intent=True`（spec §4 事实 13），题面写着「个股怎么对标」。rev1 对此既不出块也不出 gap，验收题自身有个洞。rev2 把 D11 gap 归入 P0。

顺带修正：`test_prefetch_evidence_ordinal.py` 也消费 `asof_prefetch`，rev1 回归网漏列，rev2 已补。

## 已核实基线（不要再探）

- `HEAD == gitea/main == 90c069cb`，本分支仅三份文档。
- 定向七文件集：**172 passed @ 90c069cb**（含 `test_prefetch_evidence_ordinal.py`；不含它是 167）。
- 冻结题面解析器实测：`parse_regime_intent=True`、`parse_analog_intent=False`、`parse_stock_analog_intent=True`。
- `decide_turn` 今日实测：空 manual + 冻结题 → `general_finance_qa`/「用户显式选择了工作流能力」；空 manual + 取值题 → **`stock_deep_dive`**（不是 `quick_fact`，短路把取值题一并盖住了）。
- 修复后目标值实测（走等价非 manual 路径量得）：取值题 → `quick_fact`/ops=()；冻结题 → `comparison_analog`/ops=`('history_analog',)`。
- `LoaderAndBlockTests._make_db(None, path, ...)` 跨文件复用可行（已跑通）；`_day(120)='2025-05-01'`、`_day(199)='2025-07-19'`。
- 解释器：`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`（本工作树无独立 venv）。

## 下一步

1. 本分支只 commit 三份文档，不推、不合 main。
2. 从本分支 tip 另开 `fix/operator-prefetch-os` 写代码，按 plan Task 1→2→3→4 串行。
3. 不切 8792，除非用户明示。
4. P1（做法 skill、发布层减法、Engine B/D11 的 as_of）另开，不塞进本 plan。

## 未验证 / 已知边界

- P0 只保证 **Engine A 预取路径** 的 D10 无穿越。Engine B（`ask.py:3986`）与 `stock_analogs` 仍未截断（spec §4 事实 12/14、§9 P1 4–5）。对外不得表述成「D10 已全面按截止日取数」。
- **Task 1 的期望值是实测**（上一节四条）。**Task 2/3 的 pytest 期望值是推断**——那两个 Task 的代码块照着现役源码写、逐处核过锚点，但从未执行；第一次跑出来对不上属正常，按失败断言读实际值再判，不要默认 plan 是对的。
- 全量 pytest 未在本分支跑过。`gitea/main` 上另有存量红（见 `feat/reading-rules-baseline-batch1` 交接：r2 与 main 同 4 红），Task 4 Step 3 的判据是「不比 main 多红」，不是全绿。
