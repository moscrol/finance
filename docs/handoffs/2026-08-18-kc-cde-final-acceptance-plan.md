# KC 批 C/D/E 合链 + 总验收方案（派单）

- 日期：2026-08-18
- 派单人：验收方（今晨完成批 A/B 验收、8792 链切与规程固化的 session）
- 接单人：下一个验收 agent
- 通用规程：`docs/workflows/acceptance-workflow.md`（怎么验、怎么合、怎么切、怎么回写——本单不重复，只给本批特有的队列、判据与坑）
- 验收基准总源：`docs/learning/knevo-catchup-spec-2026-08-17.md`（下称 spec；每张 PR 对应 §KC-nn 的「验收」小节）+ `docs/adr/0002-knevo-catchup-s10-decisions.md`（已拍裁决，不重议）

## 范围

做：合链 C→D→E（十张）、批次门禁、8792 链切、批 0 身份验证、spec §10 总验收四项、KC-19 门的升格。
接单人不做的：开批 F（KC-16 港股已裁决不做；KC-19 只升格给用户拍板）、重议 ADR 0002 五裁决、动题集本体、代用户 accept 判断入账。

## 1. 合并队列（链内箭头=依赖顺序，逐张验后合，不捆绑）

| 链 | 顺序 | 对应 spec |
|---|---|---|
| C 检索纪律 | #178 → #180 → #182 → #183 | KC-05 反方口径 → KC-06 两跳 → KC-07 四问 → KC-08 独立来源计数 |
| D 预测闭环 | #184 → #185 → #186 | KC-09 判断台账 → KC-10 到期裁决 job → KC-11 裁决回流 [M] |
| E 广度表达 | #188 → #190 → #194 | KC-14 海外源+别名表 → KC-15 隔夜美股映射 [D17] → KC-12 猜你想问 |

前置已核实（不用再修，但接单先复核仍成立）：#153 锚定实体修复已在 main（#157，08-17 夜合入）；max_evidence 决策单 `docs/handoffs/2026-08-17-max-evidence-stale-quota-decision.md` 已拍，C 链槽位分配须与其一致；token 已含 `write:issue`（Keychain `gitea-local` account `a77-token`），裁决写 PR 评论；patch-checker 队列已根治（`docs/verification/2026-08-18-acceptance-followups-closeout.md`）。

**完成判据**：十张全部 merged（或带裁决关闭），每张的 spec「验收」小节逐条有接单人独立复算的读数，裁决评论落在 PR 上。

## 2. 各链验收要点（spec 验收小节之外的坑）

**C 链**
- KC-05：无反方命中时必须显式披露「未检索到反方证据」，沉默=不过；live 对比修复前后 counterpoint 槽证据绑定数。
- KC-06：抽取必须确定性（词表交集+频次，零 LLM）；冻结题 B1（光刻胶）复跑看第二跳证据增量——这发同时是总验收 B1 翻绿的素材，收据留好。
- KC-07：第一版只披露不补搜——diff 里出现补搜逻辑=越界，打回。
- KC-08：依赖 claim 标记教学门（`SYNTHESIS_PROMPT_TEACHES_CLAIM_MARKERS` 历史为 False）。核 PR 怎么处理该门：若门仍关，单源标记到不了呈现层是**设计内**，验到后处理管线元数据即可，缺口如实记录，不算失败也不许翻装作到了。

**D 链**（红线密集区，ADR 0002 逐条对）
- KC-09：diff 里出现 `judgments-ledger.jsonl` 或任何第四本台账=打回；置信度出现数值概率=打回；必须是 pending→用户批处理 accept 才入账，agent 无直写权——用状态机单测+一发 live 产出候选验证，**不代 accept**。
- KC-10：裁决只追加 verdicts，不回改判断原文；夹具跑幂等。
- KC-11：召回次数/confidence 当胜率展示=打回；分母不足 N 不显示。

**E 链**
- KC-14：PQC 同题复跑命中率不得低于 #160 后基线（82 分那发）；新源条目带可信度分级。
- KC-15：与 fph2026 CLI 直查对数一致；只列映射事实，出现「必然跟涨」类推断=打回。
- KC-12：选题确定性、LLM 只润色（失败降级模板句）；澄清轮不生成；≤4 条。

## 3. 门禁与链切

十张全合后：四件套全量（workflow §3；数字对照台账最近门禁行 5428/12 只升不降）→ 8792 链切 + 三项验证（workflow §4）→ gitea 备份。

**批 0 身份验证**（链切后顺做）：launcher 的 `FORESIGHT_USER=linxiaoqi5111` **已随 2026-08-18 10:52 链切生效**（当时 launcher 已带该行），本项只做读数：生产 env 形状下 `resolve_user_id(None)` == `linxiaoqi5111`；一发 live ask 的 run 落在 `users/linxiaoqi5111/runs/`；[M]/memory_lookup 能见到 61 条 corrections（ADR 0002 实测节的数字）。

## 4. 总验收（spec §10 原判据，全部达成才算赶超收口）

1. **6 题蒸馏基准复跑**：Q1/Q2/Q4 至少两题从「Knevo 胜」翻「平/胜」；Q3/Q5/Q6 不回退。题源与历史判定：`docs/learning/knevo-vs-workbench-技能包对比台账.md`。Knevo 侧一律用 2026-08-07 探针冻结记录当对照（spec 红线），不重测对方。
2. **28 题 A/B/C 冻结集**：无回归；B1/C1/C2 三个已知失分题翻绿。题源：`docs/handoffs/2026-08-13b-night-loop-and-r15-knevo-comparison.md`（R15）。C1/C2 应已被 KC-18（批 A 已合）翻绿——复跑确认即可。
3. **收据审计**：已落地的每个 KC 项（批 A 四项 + 批 B 四项 + C/D/E 十项 + KC-18）单测+live 收据各一，列表打勾；缺=该项验收未完成，开回补单，不许「整体感觉都过了」。
4. **纪律抽查**：新增块（D7/D9/D12/D13/D17/W7/followups）逐块至少一发 live 输出人工核：零无溯源数字、零数值概率、缺数路径显式披露。

跑法：#152 sidecar live probe 旁路（避开 `/tmp/finance-8792-live.lock`），逐题收据落 `~/.finance-runtime/live-probe-traceability/`。报告：机读+人读落 `docs/verification/2026-08-18-kc-final-acceptance.md`，结果不好看原样入账，禁止为翻盘挑跑（cherry-pick）。

**完成判据**：四项各有独立报告段与收据路径；翻盘/未翻盘逐题列表。

## 5. 出口与升格

- 总验收后台账一行：四项结果 + 翻盘题清单 + 8792 revision。
- **KC-19 门**：若 ≥1 题翻盘可见 → 升格用户拍板是否开批 F（KC-19 多标的并行）；未见翻盘 → 批 F 维持不开，写明差距归因。港股（KC-16）不随结果重议。
- 顺带项（可选，别与总验收混报）：「冻结 30 题质量基线」是另一条已派单（`docs/handoffs/2026-08-18-frozen-thirty-live-baseline.md`，与 28 题冻结集**不是一回事**），其先决（数据根修复合入且生效）已齐，链切后顺跑正合适；报告分开落。

## 红线（继承 spec 尾节 + workflow，重申三条）

- 验收探针一律旁路，链切步骤之外不动 8792。
- 题集与判分器本体一个字不改；发现判分器 bug 记档另单。
- 已否方案不重走：LLM 当考官、数值概率、第四本台账、sub-agent 全家桶（spec §8「明确不抄清单」）。
