# 2026-09-22 A 股研究数据链：交付守卫改结构绑定 推送与 PR 工单

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
姊妹：#76（两题实盘复验）、#75（独立 QC）、#61（同花顺研究观察值 #810 在其内处置）。

## 背景与动机

- 09-22 真实验收（`baseline/research-data-acceptance-0922`，HEAD `f8eba1fab`，未推）：候选 `6fb37a6e` 两题各首发一次——historical-iso（历史解禁）**通过**原失败形态；financial-calc（现金流含金量）**失败**：模型抄错自己的沙箱产物（记录 `0.7474`，正文 `0.7473`），守卫 `findings` 为空。根因用最小对照钉死：`_absolute_ratio_label` 不认模型实际产出的列名 `现金流/净利润` 与措辞 `比值` → `_ratio_products` 为空 → 没有任何单元格被对账。本轮没发出去只是因为判官不可用整篇被扣下，不是守卫起作用。同时复现两条公告线索：未列名场所 `深交所互动易…[E2]` 独立来源句连引用被误删；`因此本期无任何披露文件` 漏检且 status 仍 `completed`（量具 4P/4F，控制 4/4）。**结论口径**：三个交付守卫（公告缺失、归属白名单、比率对账）都是有限词表，绑在模型自选措辞与列名上；工程绿（12259P）与 52 组变异全红只证夹具形状内的行为。
- 壳层事实：候选无条件发 `temperature`，本机网关 k3 拒收（HTTP 400 → `continuous_runtime_failed`），加 `k3_param_shim.py`（8081，仅剥 `temperature`）后复发；「判官不可用」是 `FORESIGHT_BUILTIN_LLM_MODEL` 也指向 k3、判官继承慢思考模型必超 75s 窗口，恢复 flash 后判官 `repaired`，非产品缺陷。
- 修法已在本地 `fix/delivery-guard-structural-binding`（HEAD `812f473ca`，基于 `f8eba1fab`，**未推**）：`intelligence/services/research_delivery_checks.py`——(1) 比率列按算术认定：单元格能复现该行 `ocf_cum_yi / net_profit_cum_yi` 即比率列，需两行独立吻合，词表降为额外入口；(2) 正文按数值近邻（距产物末位 1.5 单位内），整数 / `个百分点` / `bp` 不算，无产物则弃权；(3) 限定日期不是申报期；(4) 缺席 = 否定词 × 披露名词两个封闭类相乘；(5) 归属问本回合有没有披露通道证据（按工具身份，不按引用下标）。证据 `docs/verification/2026-09-22-research-data-acceptance/`：`post-fix/live-probe-before|after.json` 旧稿现判 `calculation_value_mismatch` 且只摘那一个数；`disclosure-binding/` 4P/4F → 10P/0F（含 borrowed-citation 控制组）；**61/61 拆保护必红、还原必绿**；`test_research_delivery_live_products.py` 夹具是实盘原始产物与原文，不许改措辞；`intelligence/tests` 10803P/23S/2X。既有抖动 `test_late_malformed_rejudge_cannot_masquerade_as_deadline_recovery`（deadline 0.02s）对照树也 1/3 失败。
- **已定的形态决策**：规则不能写成「模型碰巧会用的字符串清单」；比率列由算术认定、缺席由封闭类相乘、归属按工具身份；夹具用实盘原件不手写。

## 目标

1. 推送两条分支；`fix/delivery-guard-structural-binding` 开 PR（base main；`baseline/research-data-acceptance-0922` 是它的证据基座，PR 描述指向而不单独合）。
2. 前向 main；低负载四叶；抖动那条按 #59 口径四读数。
3. 阳性对照进 PR：把比率列算术认定关掉只留词表，`live-probe-after` 的实盘夹具必须回到零对账；把否定词类清空，`本期无任何披露文件` 必须回到漏检。
4. #75 独立 QC（第二方读源码 + 自造探针）。
5. 用户确认后 `merge --record`；给 #76 一张两题实盘复验条件卡：候选 = 合入后 main SHA，写手 k3 + 剥 `temperature` shim 声明，判官用 flash，首发 1 / 重发 0，判据 = 六格全对且零误报、公告句全留。

## 非目标（写死认领）

- ❌ 不跑实盘（#76）。
- ❌ 不修网关对 `temperature` 的 400（壳层测量条件，另一张单）。
- ❌ 不改历史解禁题的行为（已过原失败形态）。
- ❌ 不给 shim 转正进生产。
- ❌ 不改判官窗（#57）。

## 证据路径

| 文件 | 看什么 |
|---|---|
| 分支 `baseline/research-data-acceptance-0922`：`docs/handoffs/inflight/baseline-research-data-acceptance-0922.md` | 裁决、实盘条件、两题结果、控制组 |
| `~/.finance-runtime/reviews/research-data-acceptance-20260922-01/`、`~/.finance-runtime/convergence-20260919/retention-repair/candidate-6fb37a6e/…` | 实盘原件、`live-calculation-copy-6fb37a6e.json`、`disclosure-attribution-scope-6fb37a6e.json` |
| 分支 `fix/delivery-guard-structural-binding`：`docs/verification/2026-09-22-research-data-acceptance/`（`post-fix/`、`disclosure-binding/`）与 inflight 交接 | 修前修后探针、61 组撤保护、两条纠正 |
| `intelligence/services/research_delivery_checks.py`、`intelligence/tests/test_research_delivery_live_products.py` | 五条改法与实盘夹具 |
| `~/.finance-runtime/reviews/…/k3_param_shim.py`（实盘目录内） | 壳层适配声明形状 |

## 步骤

1. 开工三连；两棵树 clean；推送；开 PR。
2. `merge-tree` 探 main 冲突；前向；低负载四叶；抖动条四读数。
3. 两条阳性对照落 PR 评论（改坏 → 红/漏、还原 → 绿，sha256 前后一致）。
4. 交 #75；确认后合入；条件卡交 #76。
5. INDEX #71 行；inflight ≤3K。

## 验收

- [ ] PR head 四叶收据 revision == head。
- [ ] 两条阳性对照各有「改坏读数 / 还原读数 / 指纹一致」三项。
- [ ] `test_research_delivery_live_products.py` 的夹具文件哈希与实盘原件一致（不许改措辞）。
- [ ] 合并记录含授权原话与出处。

## 红线

- 只用 pathspec 提交；合入 main 等用户确认；不强推。
- 不跑真实模型；8907 / 8081 旁路端口保持已停；不动 8792。
- pytest / ruff 一律 `.venv-workbench/bin/python -m …`。
- 夹具用实盘原件，脱敏但不改措辞；不写明文密钥。
