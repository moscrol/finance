# 工单：宽度共振袋 + 快照产物完成判据（2026-08-26）

- 状态：**P1 已落地**（#418 @`e8024dd9` 合入、8792 已切 `c0226f34`，`R-20260826-02` confirmed 带成立条件——sw_l1 映射缺口见台账回读；P0 的待做项（daily-full skill 完成判据）仍开放，归 daily-full 工作流认领）
- 来源：双臂对照 `~/.finance-runtime/trace-diff-spt-forward-20260826/`（react 臂 vs 8792 产品臂，同题同画像）
- 台账：`R-20260826-01`（P0）/ `R-20260826-02`（P1），见 `docs/prediction-ledger.md`
- 纪律边界：`docs/superpowers/specs/2026-08-24-market-watch-component-first-design.md` §0.2——组件只交付事实，不给判语；禁止加 prompt / 内嵌 ReAct 追产品分。

## P0 · market_snapshot 纳入修复完成判据（防复发，改文档不改代码）

**事实**：08-26 00:16 的 0825 修复补齐 DuckDB + 复盘产物后判 COMPLETE，但 `market_snapshot/` 最新仍是 `2026-08-24.json`。`api/app.py::_runtime_market_reference_date` = `min(snapshot served_trade_date, DuckDB max)`（刻意保守），于是生产问答整日站在 08-24，而 health/覆盖率全绿——「行数正常值是空壳」的同族失败形状：单点审计抓不到，只有跨臂/跨日对照能抓到。

**已做**（2026-08-26 15:41）：`PYTHONPATH=$FINANCE_WS .venv-workbench/bin/python scripts/sync_market_snapshot.py --date 2026-08-25` → provider=duckdb_exact / quality=complete / fresh；复算 min() = 2026-08-25。正对照 run 见台账 `R-20260826-01` 回读。

**待做**：`skills/daily-full-review/SKILL.md` 的修复/补跑完成判据加一条——「`market_snapshot/latest.json.served_trade_date` == 当次修复的交易日，否则不算 COMPLETE」。该 skill 归 daily-full 工作流所有，改动走它自己的树，不要顺手夹带。

## P1 · market_watch 新增「宽度共振袋」

**动机**：SPT 类画像的高频判据「概念板块与申万行业共振（宽度夺价）才确认主线扩散」完全可结构化，但产品臂本轮只引用了判据文本、没做数据验证；react 臂做了验证拿到反证（概念 +4.9% 放量 vs 对应 sw_l1 为负），据此把结论降了一级。这是两臂最大质量分差点，且属于「供数侧缺袋」不是「模型不会」。

**形状**（袋内容 = 事实对照行，不带判语）：

```sql
-- 站立日 = 与其余袋同一 served_date（复用 _standing_on_or_before，无第二套口径）
-- 输入：本轮 subject 命中的概念板块名单（或当日 diff_ratio 前 N 概念）
SELECT s.sector_name, s.pct_chg AS concept_pct, s.diff_ratio, s.amount,
       s.sw_l1, w.pct_chg AS sw_l1_pct
FROM fact_sector_daily s
LEFT JOIN fact_sw_l1_daily w
  ON w.sw_l1 = s.sw_l1 AND w.trade_date = s.trade_date
WHERE s.trade_date = ?
```

渲染成「概念 X：+a%/边际量 b%；对应一级 Y：c%」若干行；`sw_l1` 缺映射或当日无行时如实写「缺数」，认不出来 fail closed（不渲染判断）。

**落点**：`intelligence/services/asof_prefetch.py` 新 operator + `market_watch_pack` 渲染；挂进现有 prefetch 程序（与四袋同 served_date、同预算截断纪律：限定语排在被限定内容之前）。

**验收**（预注册在 `R-20260826-02`）：
1. 离线：袋渲染单测红→绿；served_date 一致性断言；缺映射 fail-closed 用例。
2. live 同题双态（有/无该袋），对照样本 = 本工单来源目录那对分叉。
3. 开关板登记原子行（seam + close_via + positive_control），棘轮 id 只增——见 `docs/handoffs/inflight/feat-capability-switchboard.md` 下一步 §1。
4. 失败形状即停：加袋后模型忽略袋内容仍给主线级结论 → 按 §0.2 停止供数侧加料，问题改挂解读层。

## 不要做

- 不要把「逆势放量扫描」「板块选择」也顺手组件化——前者可以另立工单（同样纯 SQL），后者是判读不是供数（§0.2 反模式）。
- 不要为了追平 react 臂在 system prompt 里加「请先查申万一级」。
- 不要动 8796（复核服务故障未修，D 臂不可比）。
