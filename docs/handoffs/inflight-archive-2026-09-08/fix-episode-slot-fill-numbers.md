# fix/episode-slot-fill-numbers

## 这个分支做什么
子单 B：必填格数字从**预取行与带收据的工具行**填入（spec §6.2 两半都齐了）。十刀覆盖预取/工具/判官/repair/数据层；live 仍未进 episode 引擎。

## 当前状态
**已收口（2026-08-21）**：#289 已合入 main（merge `6320b3bc`），8792 已切同 rev。live 双臂过：CXO 同题 B 臂 `run_20260821_164659_624916` 判官零删句、31/31 数字有出处（上午 A 臂同题删 65%）；减肥药新题 `run_20260821_165210_889002` 七节点逐位对库真。「live 仍未进 episode 引擎」一句已过期——生产即 episode 引擎，无需再搭 sidecar。台账 `R-20260821-02` → `confirmed`，`-04` 修后样本 2/3。收口详情见 `docs/handoffs/inflight/main.md` 2026-08-21 行。以下为合并前历史状态。

干净树从 `gitea/main`@`dfc25221` 长出。**PR #289 open（原 23 笔）+ 新 2 笔未推**。工作树干净。
十刀：1 预取观察值 `98a02774` → 2 删句记缺口 `1384a33a` → 3 槽补真值 `fe8555e0` → 4 数值门禁认观察值 `83f671ce` → 5 核对从判官拿走 `794d2acb` → 6 不可达投递 trace `135354c1` → 7 同日多行标口径分歧 `11731551` → 8 缺口按丢失原因分流 `907f2938` → 9 撞名棘轮审计 `cb91fa73` + VIEW 口径 `6d32a715` → **10 工具行观察值 `f0ad6cfb`**（sector_daily/sector_stock_daily 行级明细挂 StructuredObservation；矛盾格不产=第 7 刀同规则；聚合/无主体/未登记数据集 fail closed；消费端零改动）。
一次回退：`f552946b`（「不可达」升级为跳过修复轮，判据看不见 salvage）。

第 10 刀的立据 run：`run_20260821_152044_472523`（8792@dfc25221 生产，CXO概念发酵题）——预取被短 subject 挤空后模型靠 finance_query 自救写出全真草稿，判官删 65% 时这些工具行数字无观察值保护，静默消失。全程 trace diff 见主检出树 `docs/verification/2026-08-21-tracediff-cxo-ceiling.md`（未提交）。
该 run 同时更正一个归因：**判官投影 C1–C4（`82a9fac6`）已在 main 上 live**，`projection_ordinal_mismatch_count=0`；残余机制是投影 spec §4/§8 刻意留下的 **A3 写手 binding 缺口**（29/47 卡未绑定→不送判官→引用被判不存在）。数字侧由第 4 刀观察值豁免 + 第 10 刀合围；散文侧仍无保护（见下一步）。

## 未验证 / 已知边界
- **live 未进 episode 引擎**：手搭 sidecar 与生产不等价，读数作废。别再手搭；先解 `scenario_tree` 预检在非生产环境必败。
- 槽只在 judge repair 路径补真值，正常写稿路径未消费 `observation_value`。
- `agent_episode.py`「否则删去数字」仍在提示词，归子单 C。
- `dual_red_counts` 预取行还没出 observations。
- 审计未接 daily-full；worktree 无 db/ 时跳过并明说「不是通过」。
- gitea/main 存量红：prefetch 事件未进 `DURABLE_EVENT_KINDS`（另案）。

## 下一步
1. live 验十刀——先有能进 episode 的 sidecar，不要再手搭。
2. prefetch 事件登记进 durable-kind 表（main 存量红，可顺手）。
3. `audit_sector_name_collisions.py` 接 daily-full 收尾（手跑 → 同步后跑）。
4. 合入等用户确认；**未切 8792**。与 #288 仅 `asof_prefetch.py` 小幅重叠（hunk 基本不相交），后合方 rebase。
5. 未立项决策（别顺手做，先论证）：① 正文 E 引用经 `resolve_evidence_refs()` 自动 resolve 进 binding——保护散文真话，但可能松动「only answer-bound evidence」纪律；② chain_mapping 契约矛盾（evidence 模式禁权重知识 + 必填 + KB 无链路证据 = 结构性不可满足）。

## 踩过的坑
- **重叠 ≠ 代码数**：换代两段不重叠不报；按代码数判会永久红灯。
- **读 VIEW 不读 generation**：物理表分代同日多行是快照，不是撞名。QC 前 PCB 27→VIEW 25。`check_sector_fact_access` 拦名单外读物理表。
- 撞名不进 pre-commit：由写数据引入，commit 时拦错对象；worktree 无 db/ 会天天误红。
- 引用卫生 ≠ 真伪判据。不要给含真值的句子免死金牌。
- 「某条路走不通」≠「整件事做不了」（`f552946b`）。

## 已验证
第 9 刀 QC：41 passed；层门禁 0 违规；红队 摘「钙钛矿电池」认出新增、小金属 100→406 认出恶化。基线 128 名，VIEW 口径 PCB=25 / 钙钛矿=24 / 小金属=406。
第 10 刀 QC：新测 6P（TDD 先红 4）；变异（矛盾格抑制改坏）转红、还原复绿；邻域回归 95P/8skip（finance_query×4 + slot + judge-delete + repair 文件）；判官全量 170P；ruff 干净；9 道 pre-commit 门禁全过。
