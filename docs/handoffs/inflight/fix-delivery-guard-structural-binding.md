# 交付守卫改结构绑定（fix/delivery-guard-structural-binding）

基于 `baseline/research-data-acceptance-0922`（含 6fb37a6e 业务码）。未 push / 未开 PR / 未合 / 未部署 / 未经独立复核。

## 病根（两处同一个）
规则写成「模型碰巧会用的字符串清单」，词却由被校验方自己选。
- 比率列靠关键词认，列名由模型起（两次实盘叫 `现金流/净利润`、`OCF/归母净利润`）：没认出→零格对账→
  抄错的 `0.7473`（记录 `0.7474`）原样交付。
- 缺席靠短语枚举：`本期无任何披露文件` 漏检而同义的 `零披露` 拦得住；归属靠场所白名单：
  引 `深交所互动易` 的句子连引用被误删。

## 改法（`intelligence/services/research_delivery_checks.py`）
1. **比率列按算术认定**：单元格能复现该行 `ocf_cum_yi / net_profit_cum_yi` 即为比率列（指标名出自数据契约、
   脚本改不动），需两行独立吻合；词表降为额外入口。
2. **正文按数值近邻**：距该期产物末位 1.5 单位内＝在说这个产物；正确四舍五入仍正确，无产物弃权。
3. **限定日期不是申报期**：`2025年报（截止X，披露Y）` 原读成三个期，作用域提前截断，错误数字正落在外。
4. **缺席＝否定词 × 披露名词**（两封闭类相乘），不再枚举组合结果。
5. **归属问本回合有没有披露通道的证据**（按工具身份；不按引用下标——别名是投影的、会偏移）。

## 证据（`docs/verification/2026-09-22-research-data-acceptance/`）
- `post-fix/live-probe-before|after.json`：旧稿现判出 `calculation_value_mismatch`，只摘那一个数
  （`615.22/823.2/2192.48` 全留）；修后新跑实盘六格全对、零误报
- `disclosure-binding/`：量具 **4P/4F → 10P/0F**（含 borrowed-citation 控制组：别通道的引用不能洗白同一句）；
  真实实盘正文 4 句涉披露句全留、0 findings；**61/61 拆保护必红、还原必绿**，baseline/restored-full 各 708 执行 0 失败
- `test_research_delivery_live_products.py`：夹具是实盘原始产物与原文，**不许改措辞**（手写夹具会继承守卫的词）
- 旧四支量具 6/4/16/14 全过；全量 `intelligence/tests` **10803P/23S/2xfail**

## 两条纠正
- 「判官不可用」是**壳层**造成：`FORESIGHT_BUILTIN_LLM_MODEL` 也指向 k3，判官继承慢思考模型必超 75s 窗口
  （保险丝只能调小）；恢复 flash 后 `repaired`，非产品缺陷。
- 既有抖动（非本次引入）：`test_late_malformed_rejudge_…_deadline_recovery` deadline 仅 0.02s，加负载后
  对照树 14504b65c 与本树各 1/3 失败——已用对照归因，勿当回归。

## 合流自探（未 push/未 fetch）
`merge-tree`：对本地 `main` 仅 `.claude/lessons_learned.md` 冲突；对 `gitea/main`（领先 208 提交）还冲突
`episode_semantic_verifier.py`（分歧约 690 行）、`continuous_turn_adapter.py`、`docs/agent-product-door.md`。
合流要在 verifier 上解冲突，解完必须重跑本页全部读数。

## 红线
8907/8081 已停；8792 未动；主树他人改动未碰。

