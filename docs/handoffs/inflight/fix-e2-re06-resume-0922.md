# fix/e2-re06-resume-0922（在飞）

base `a2c8d1f90`（gitea/main）。树：`/Users/a77/fwp-wt-e2-re06-resume-0922`。
两个提交，未合并/未推送/未部署。

## 1. `8fd6882ea` E2：local_only 按原题号逐题交付

用户自己编了号时按原号冻结 `answer_qN` 必需槽（未编号本地题、full 题形状不变），
一处实现供提示词/判官/语义修复保号/公开稿复验。分界只写在**结清口径**上
（本轮唯一设计判断）：`material_only` 零读权限，交代缺项是唯一诚实交付，
`legal_gap` 可结清；`local_only` 手里有本地读工具，再认 `legal_gap` 等于用
「缺少X」买断取数义务，故本地题缺口回到普通 `required_output_gap`。
改动五文件，详见提交信息；一个坑：跨轮恢复不变式的判据用「契约已有
`answer_q*`」而非「有编号问题」，否则改动前落盘的会话一恢复即报错。

## 2. `8975ce0f2` RE06：写读同意折叠抽共用

第九轮复核只证明写侧门与 05 读侧在**当时快照**上五条轴一致，那不是结构保证——
任一侧改折叠，另一侧不会变红，后果是「写了读不到」或「已撤回仍进读数」。

新增 `product_value/consent.py`：`scopes_at`（排序键 `(effective_at, action)`、
`> at` 截断、grant/withdraw 集合运算）+ `covers_measurement`。排序键全仓只剩一处。
`measure._scopes_at` 与 `run_observer._measurement_consented` 改为调用它。

**有意差异不进共用件**，留在各自调用点并写进 docstring：读侧只认带 `participant_id`
的试点记录、无记录返回 None（未知）；写侧认 owner 自己的记录、无记录按自用默认
放行；坏时间戳读侧照抛、写侧跳过——统一它等于把跳过的一条 withdraw 变成「已撤回
当仍授权」。行为零变化，不加门页条目。

## 已验证
- `test_e2_local_question_delivery.py` 20 条（基线 15F/4P → 20P）；变异 7/7 被杀。
- `test_re06_consent_fold_shared.py` 18 条（折叠单元 + 真实台账写读对拍 + 两处
  有意差异锁定 + 共用函数结构桩）；变异 8/8 被杀。「收走读侧 participant_id 过滤」
  最初存活（落到 "None" 键、当前无可观测后果），补
  `test_read_side_timeline_admits_pilot_records_only` 钉住「自用记录不得进试点读数」。
- 全量 10624 passed / 23 skipped / 2 xfailed；另 `test_rag_worker` 一条负载敏感
  flake（单跑 47/47 绿，与 product_value 零引用，非本次引入）。

## 未做 / 边界
- 作者自验，非独立 QC；P7 隔离验收（全新会话+原始 T3 文本+真实模型）未做。
- 未编号的本地多问题仍落 `direct_answer` 一格：编号是唯一确定性判据，刻意不动。
- RE06 残留 P3 两项仍开：门读取在事务外（TOCTOU）、部分授权翻自用默认的 UI 文案；
  F2 前端同意入口仍缺（见 `docs-qc-re06-i11-50074c76.md` 补记）。

## 下一步
P7 隔离验收（需真实模型，用户定）／RE06 真人试点／TOCTOU 收口。
