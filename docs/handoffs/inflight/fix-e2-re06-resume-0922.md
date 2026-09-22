# fix/e2-re06-resume-0922（在飞）

base `a2c8d1f90`；gitea/main 已前进 7 提交，全在 `market_feature_store` 侧，与本枝
零重叠。树 `/Users/a77/fwp-wt-e2-re06-resume-0922`，四个提交，未合并/未推送/未部署。

## 1. `8fd6882ea` E2：local_only 按原题号逐题交付
按原号冻结 `answer_qN` 必需槽（未编号本地题、full 不变）。**结清口径不跟着共用**：
`material_only` 零读权限，交代缺项即诚实交付，`legal_gap` 可结清；`local_only` 有本地
读工具，认 `legal_gap` 等于用「缺少X」买断取数义务，故回普通 `required_output_gap`。
坑：跨轮恢复判据用「契约已有 `answer_q*`」而非「有编号问题」，否则旧会话恢复即报错。

## 2. `8975ce0f2` RE06：写读同意折叠抽共用
复核只证明两侧在**当时快照**上一致，那不是结构保证。抽出 `consent.py::scopes_at`
+ `covers_measurement`，排序键全仓只剩一处。**有意差异不进共用件**：读侧只认带
`participant_id` 的记录、无记录返 None；写侧认 owner 记录、无记录按自用默认放行；
坏时间戳读侧照抛、写侧跳过——统一它等于把漏掉的一条 withdraw 变成「已撤回当仍授权」。

## 3. `8cb1b4929` RE06：同意门锁内复核（TOCTOU）
门在锁外读台账，到抢锁之间 API 侧可追加撤回，老实现不再看一眼就写。**修复前实测
真的写出了 run_started**。改为在 `try_transaction` 内复核同一谓词（读 txn，不是锁外
再读一遍——那只是缩小窗口，变异 T2 专门守这个伪修法）。锁外那道门保留：让本就不
该写的情形不去抢锁（QC Q9）。**时间语义不变**：按事件自身时刻判定，未来生效的撤回
不追溯；改写时语义会让门比读侧严、凭写入延迟丢事件。代价：锁内多读一遍台账
（`append_once` 本就读全表，量级不变）；坏台账 stderr 两行变三行。

## 未做 / 边界
- 作者自验，非独立 QC；P7 隔离验收（全新会话+原始 T3 文本+真实模型）未做。
- **跑全量前先看 `uptime`**：本机常有十几棵树并发跑 pytest（实测 load≈80、17 个
  pytest 进程）。`test_rag_worker::test_warm_worker_survives_first_timeout_...` 会因此
  假红——同一提交 `8975ce0f2` 两次全量一红一绿，别去「修」它。
- RE06 残留 P3 仅剩一项：部分授权翻自用默认的 UI 文案；F2 前端同意入口仍缺。
- 未编号的本地多问题仍落 `direct_answer` 一格（编号是唯一确定性判据，刻意不动）。

## 已验证
- 新测试三份（E2 20 条、折叠 18 条、TOCTOU 6 条）均先红后绿；变异 7/7、8/8、5/5 全杀。
  折叠那轮「收走读侧 participant_id 过滤」最初存活（无可观测后果），补测钉住
  「自用记录不得进试点读数」。
- 回归：RE06 十一套 186 passed（含 i11 真实 API 端到端）；全量 10630 passed /
  23 skipped / 2 xfailed（含上述假红）。
