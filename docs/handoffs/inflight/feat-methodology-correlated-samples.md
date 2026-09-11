# feat/methodology-correlated-samples · 工单 #48（OPT-05 第一刀）

## 这个分支做什么
同日共振与重叠窗口不再冒充独立证据。三件事：`stats.block_bootstrap_readout`（日期块重采样，块长 = `rule.success.horizon`，事件不展平、块内相关性原样保留；块不足 `insufficient_blocks` 不回落二项检验）、`stats.combined_verdict`（顶层四态 = 独立假设 × 依赖感知的保守合成，refuted 同样要两道——同日负样本同样不独立）、`runner._purge_cut_date`（窗末 horizon 个交易日内事件的 outcome 伸出窗外 = 跨窗标签泄漏，剔除并入账）。收据新增 `dependence` 段与 `events.n_purged_cross_window / purge_cut_date`；`RECEIPT_SCHEMA` 未升版，旧收据仍可读。工单 `2026-09-11-methodology-correlated-samples-workorder.md`。

## 决策与被否方案
- 块长 = success.horizon（盖住 outcome 重叠范围），v1 冻结；否了逐日自适应——spec 要求先冻结更新协议。
- 种子固定 20260911 平铺入收据；换种子 = 换口径须走版本。
- refuted 也要两道一致；否了「证伪豁免依赖门」——「推翻不用预注册」是晋升流程的不对称，不是显著性豁免。
- 阶段桶 verdict 保留独立口径（解释用，晋升只看顶层合成）；否了桶级依赖读数——桶内事件日更少，全会 insufficient，等横截面样本量再议。
- 簇计数用自然日间隔（交易日距离下界，断簇偏松、簇数只多不少），只报不判。
- 合成夹具 120→240 日：120 日只有 36 个事件日 = 7 块，真阳性也会被依赖门拦——门要拦「事件多日期少」的形状，不是拦掉夹具。

## 当前状态
基线 = 工单 #42 认证分支尖 `c3e9ff97`（含 OPT-04 两刀 + gitea/main@c714eb60）。本刀改动已落待提交推送（见本文件同提交）。**合并顺序：#42（PR #681）先合，本分支 PR 后合**——lifecycle/receipts 变更来自 #42。

## 已验证
- `test_methodology_dependence.py` 15 条（复制不提升证据 / 种子幂等 / 合成矩阵 8 组 / 全负块不足不出 refuted / 簇计数 / purge 端到端 / 收据段）。
- `test_methodology_backtest.py` 69 + lifecycle 38 + experience_cards 全绿（合计 127+15）；阳性对照在依赖口径下 supported、前视翻转在 240 日夹具下 refuted。
- ruff 0。全量 pytest 后台跑（读数见 PR / 后续回写）。

## 未验证 / 已知边界
- 未跑真库三条种子规则重读（旁路库在主树；真库读数会更保守——事件日少的规则会从 not_distinguishable 掉 insufficient_n，这是预期）。
- 尝试账（登记先于执行、多重检验分母、留出访问登记）未做——OPT-05 后半，需先登记台账地图，另开刀。
- `_summarize_horizons` 描述表未接 purge（不进 verdict）。

## 下一步
1. #42 合入后本分支开 PR（diff 自动缩到本刀）；用户确认合并。
2. OPT-05 第二刀：尝试账。
3. 真库 `run --stage discovery` 对三条种子规则出首批带 dependence 段的收据。
