```json
{
  "claims_examined": [
    "C2: 并跑表源上界为 max(spec.gap_parallel)（live_parallel 查询 BETWEEN window_start AND max(gap_parallel)，行274-281；src_a 截止 seg_a_end，行341-346）——上界外合法后继历史不应误拒、不应进入授权源/LAG 前驱链",
    "C2: adjusted='none' 过滤——缺口日仅有 adjusted='hfq' 行时视为缺日，应部分态拒绝",
    "C2: 无效输入（源行 close 非 NaN/inf，_finite）与部分态（live_parallel≠spec 且非空）均须写前 _fail 拒绝，不得发布",
    "C3(次级): _accept(593-722) 以 bf_src/bf_pq 独立重算 oracle（前市场日 close 量化 0.01 的 pre_close、独立 pct/amount/volume 公式）、回填行 turnover 必须为 None、保留行含 updated_at 全列快照逐列相等、09-11 钉值双校验、window 黄金三元组双向集合相等——源与 oracle 口径一致的静态证据成立，行为验证留待执行阶段"
  ],
  "limits": "explore 请求已用 4（2 读输入 + 2 读源）+ 2 写 = 在 17 内；未执行任何命令；未读全 CLI/_apply_main/_rebuild_derived；未触碰生产、网络、git、候选写。探针仅覆盖 _guard 的 C2 行为与 C3 静态一致性，_accept 的运行时 oracle 一致性未在探针中执行（fixture 需 bf_src/bf_pq 临时视图，属执行阶段）。",
  "next_stage_commands": [
    "/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260924-01/spec/work/probe_c2_guard.py --confcutdir=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260924-01/spec/work -p no:cacheprovider --basetemp=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260924-01/spec/work/tmp/pytest -q"
  ],
  "out_of_scope": [
    "C1",
    "C4",
    "C5",
    "C6",
    "C7"
  ],
  "probe_files": [
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260924-01/spec/work/probe_c2_guard.py"
  ],
  "summary": "PR #813 独立规格复核（仅 C2/C3，不整体批准）。已读 claims.md、source-map.md 及 _guard(239-381) 与 _accept(593-722) 源码。C2 关键代码事实：live_parallel 查询上界为 max(spec.gap_parallel) 且限定 adjusted='none'；live_pq 排除已存在主表行且 > max(gap_parallel)；部分态（live≠spec 且非全空）与已闭但行数不符均 fail closed；源集合须与市场历逐日相等且 close 有限。C3：_accept 以 bf_src/bf_pq 独立 oracle 逐字段复核回填行、保留行全列（含 updated_at）快照、09-11 双钉值、window 黄金三元组。已写 1 个探针 probe_c2_guard.py（4 用例：上界外后继历史不误拒不污染源、hfq-only 缺口日拒绝、NaN close 拒绝、部分态拒绝），本阶段按要求未执行，命令见 EXPLORE.md。",
  "complete": true,
  "stage": "explore",
  "axis": "spec",
  "revision": "3c5b3c9a6f0c1fe9401c424bc5ac396cf46fbc59",
  "baseline": "4cc15e703f81bce8abadee00f68caacdb0c72b4d"
}
```
