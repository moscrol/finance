# 材料题「一句一 claim」改为 harness 切句：离线证据（2026-10-04）

FINANCEWORKS-6 的单因素改动。只改「多句 claim 怎么处理」：从整稿退回作者、耗一轮修复，改为公开正文按作者原文发布，
只把 claim 绑定按 `claim_sentences()` 的边界切开，每片继承原 claim 的 kind、来源锚点与历史字段。作者提示词不变。

## 为什么改

- 用户纠偏 `d0abda287494`（10-02）与 `65961f19bae1`（10-03）：harness 优化应改善任务、证据与错误反馈，
  不靠坏例硬规则；下一片优先退出被替代的硬编码裁决。model-owned spec §7.1 把「每句必须拆成固定子断言」
  列为不再默认要求的形式。
- 冻结源：2026-09-28 真实 Workbench 材料题（glm-5.3，authoring-v2 四臂），裁决
  `closeout-0929/answer-audit/adjudication-final.json`：19 份答卷 usable 2 / partial 10 / unusable 7。
  **7 份 unusable 全是交付失败**（4 份未交付公开答卷、3 份「现有证据不足」缺口模板），没有一份是内容判错。
- 首错（arena 只读诊断 `task6-first-error-20261004/`）：12 条可追 run 中 10 条的第一个 invalid_action 是
  `bad_claim_binding: claim rendering requires one sentence per claim`。
- 既有事故：`run_20260917_004950_254515` 判官理由已送达、作者已改对内容，修复稿因两句塞进一条 claim 被
  `invalid_repair_finish` 直接终局（见 `test_repair_round_restates_the_frozen_wire_format_it_still_demands`）。

## 离线重放（零模型调用）

方法：取每个 run 的首个 `model_turn.content`，用冻结 `contract` 重建 context，调 `validate_episode_finish`。
对照列是现行 main / 生产代码 `ae02f420d`，改动列是本分支 `cf14e8498`。只判结构合法性，即能否不耗修复轮进入
语义复核；**不判内容对错**。

| 臂 | 题 | run | 现行代码首稿 | 本分支首稿 |
|---|---|---|---|---|
| legacy | history | `run_20260928_183340_272055` | bad_claim_binding | bad_claim_binding |
| legacy | transmission | `run_20260928_183420_507196` | bad_claim_binding | PASS |
| legacy | news | `run_20260928_183555_876585` | bad_claim_binding | PASS |
| legacy | comparison | `run_20260928_183721_229409` | bad_claim_binding | PASS |
| legacy | financial-holdout | `run_20260928_184043_910396` | bad_claim_binding | PASS |
| compact | history | `run_20260928_190840_926822` | PASS | PASS |
| compact | transmission | `run_20260928_190856_107907` | bad_claim_binding | PASS |
| compact | news | `run_20260928_191006_448615` | bad_claim_binding | PASS |
| compact | comparison | `run_20260928_191131_801979` | bad_claim_binding | bad_claim_binding |
| compact | financial-holdout | `run_20260928_191211_987504` | bad_claim_binding | missing_evidence |
| compact | fact-r1 | `run_20260928_191327_291812` | unknown_evidence_ref | unknown_evidence_ref |
| method | transmission | `run_20260928_192238_240518` | bad_claim_binding | material_quote_mismatch |
| method | financial-holdout | `run_20260928_192308_432235` | bad_claim_binding | material_quote_mismatch |
| method | news | `run_20260928_192343_646942` | bad_claim_binding | PASS |
| method | comparison | `run_20260928_192438_862539` | bad_claim_binding | PASS |
| quote-repair | history | `run_20260928_200957_052796` | historical_excerpt_shape | historical_excerpt_shape |
| quote-repair | comparison | `run_20260928_201012_179141` | bad_claim_binding | PASS |
| quote-repair | financial-holdout | `run_20260928_201117_433340` | bad_claim_binding | material_quote_mismatch |
| quote-repair | news | `run_20260928_201232_709081` | not_json_object | not_json_object |
| quote-repair | transmission | `run_20260928_201413_021994` | bad_claim_binding | private_material_reference |

**首稿结构合法：1/20 → 10/20。**

反向对照：改动后引用不逐字（`material_quote_mismatch` ×3）与私有材料 ID 外泄（`private_material_reference` ×1）
照样拒收。仍拒的另两条 `bad_claim_binding` 与切句无关，分别是「claim fields must be strings」和
「unsupported author fields」，属于模型输出 schema 违规。

改动后仍拒的 10 条按成因分：来源完整性 4（应保留为硬约束），输出 schema 4（JSON 破损、字段类型、未知字段、
历史摘录形状，是下一个交付因素），系统附加槽 `evidence_boundary` 缺证据 1，未知证据序号 1。

## 没有放松的东西

- 逐 claim 复核粒度：切完仍是一句一 claim，判官看到的句子与绑定按同一函数切分。
- 来源核验：逐片检查锚点逐字、未知材料、历史坐标；私有标识与槽位覆盖检查不变。
- 反馈坐标：错误位置映射回作者写的 claim 序号（`claim_origins`），同一 claim 的切片报同一处、合并一条，
  不出现作者稿里不存在的 `claims[1]`。
- 公开正文：按作者原文与原段落发布，跨句的 Markdown 强调不被切断。

## 测试与变异

- 7 个相关测试文件 459 passed。原 4 条「多句即报错」测试改为断言新行为；3 条修复机制测试改用引用不逐字作
  触发器，被测的是修复链路，不是切句；1 条多句批量报错测试删除，其代码已删，引用错误的有界反馈已由
  `test_material_quote_recovery.py` 覆盖。
- `scripts/mutation_check.py` 5/5 KILLED：去掉切句、反馈坐标用切片序号、切片丢锚点、原地改写调用方 payload、
  切句边界与判官不一致。M1 的报错显示：如果以后删掉切句，多句 claim 会落到下游完整性检查，被当作
  `material_source_violation` 硬拒，比原来的格式错误更重。这一点已由测试钉住。
- 全量门禁读数贴在 PR 评论里（提交交接后再跑，读数不回写本文件）。

## 不能据此宣称的

- 内容正确性与模型收益：多交付出来的答卷仍带首个 model turn 的推理错误（现金流口径等）。这条只回收
  harness 自身造成的交付损失。
- 真实端到端交付率：修复轮、判官与终局阶段没有重放。是否真的多交付，需要按预注册在未调参的留出题上做
  GLM 同模型旧版 / 新版配对。
- n=20 来自同一批冻结题，四臂共享题面，不能当成独立样本的统计结论。

## 产物

`~/.finance-runtime/reviews/claude-takeover-20261004/`：`replay/`（脚本、`replay-result.json` 为对照列，
`replay-result-impl.json` 为改动列，code_revision=cf14e8498）、`mutation/`（spec、summary）。
