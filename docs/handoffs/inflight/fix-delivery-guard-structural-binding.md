# 交付守卫改结构绑定（fix/delivery-guard-structural-binding）

基于 `baseline/research-data-acceptance-0922`（含 6fb37a6e 全部业务码）。未 push、未开 PR、未合 main、未部署。

## 为什么改
实盘验收查出：比率对账守卫在真实会话里**零覆盖**。它先要认出「哪一列是比率」，判据是关键词表；
而列名由模型自己起——同一道题两次实盘分别叫 `现金流/净利润` 和 `OCF/归母净利润`。
第一次没被认出 → 产物集合为空 → 没有一格被对账 → 抄错的 `0.7473`（记录 `0.7474`）原样留在稿里。

## 改了什么（`intelligence/services/research_delivery_checks.py`）
1. **比率列按算术认定**：某列的单元格若能复现该行报告期的 `ocf_cum_yi / net_profit_cum_yi`，即为比率列。
   这两个指标名来自财务数据契约，脚本改不动。需**两行独立吻合**，单格巧合不能提列。词表保留为额外入口。
2. **正文不再要求本地比率标签**：距该期产物末位 1.5 个单位以内的数被视为「在说这个产物」；更远的是别的事实。
   正确四舍五入仍正确（0.7474 显示成 0.75），整数 token、`个百分点`、`bp` 不算水平值，没有产物则弃权不裁决。
3. **`2025年报（截止 …，披露 …）` 是一个期 + 给它标日期**：把限定日期读成第二个申报期会提前终止作用域，
   错误数字正落在作用域之外——这是它躲过所有检查的第三个原因。

## 证据（`docs/verification/2026-09-22-research-data-acceptance/`）
- `post-fix/live-probe-before.json`：旧那篇被扣下的草稿，现在判出 `calculation_value_mismatch`，只摘那一个数，`615.22/823.2/2192.48` 全留
- `post-fix/live-probe-after.json`：修后新跑一次实盘（写手仍 k3，判官恢复 flash），答案发出、六格全对、零误报
- `post-fix/mutations-summary.json`：**57/57 拆保护必红、还原必绿**；baseline 与 restored-full 各 695 执行 0 失败
- `intelligence/tests/test_research_delivery_live_products.py`：夹具是那次实盘的原始产物与原文，**不许改措辞**
- 旧四支只读量具在新版本重跑：6/4/16/14 全过；全量 `intelligence/tests` 10782 passed / 23 skipped / 2 xfailed

## 纠正一条旧结论
上版交接写「判官不可用需单独定位」——那是**壳层造成的**：`FORESIGHT_BUILTIN_LLM_MODEL` 也被指向 k3，
判官继承慢思考模型必然超时 75s 窗口（该窗口是保险丝，只能调小）。恢复 flash 后判官返回 `repaired`。

## 仍未收口
- **公告线索两条未修**：`check_disclosure_attribution_scope` 仍 4P/4F。`_ABSENCE`/`_ATTRIBUTED` 还是词表，
  病根与本次相同（绑在模型措辞上），但改法不同——要做断言类型识别，不是再补词。
- 本分支**未经独立复核**。合流前按 `docs/workflows/acceptance-workflow.md` 自算读数、`git merge-tree` 自探冲突。

## 红线
8907/8081 已停；8792 未动；主树他人改动未碰。
