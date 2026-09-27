# fix/e2-re06-resume-0922（在飞）

base `a2c8d1f90`；gitea/main 新提交全在 `market_feature_store` 侧，与本枝零重叠。
树 `/Users/a77/fwp-wt-e2-re06-resume-0922`，六个提交，未合并/未推送/未部署。

## 1. `8fd6882ea` E2：local_only 按原题号逐题交付
按原号冻结 `answer_qN` 必需槽。**结清口径不共用**：`material_only` 零读权限，交代
缺项即诚实交付，`legal_gap` 可结清；`local_only` 有本地读工具，认 `legal_gap` 等于用
「缺少X」买断取数义务，故回普通 `required_output_gap`。坑：跨轮恢复判据用「契约已有 `answer_q*`」而非「有编号题」，否则旧会话一恢复就报错。

## 2. `8975ce0f2` RE06：写读同意折叠抽共用
复核只证明两侧在**当时快照**上一致，不是结构保证。抽出 `consent.py::scopes_at` +
`covers_measurement`。**有意差异不进共用件**：读侧只认带 `participant_id` 的记录、无
记录返 None；写侧认 owner、无记录按自用默认放行；坏时间戳读侧抛、写侧跳过——
统一它等于把漏掉的 withdraw 当成仍授权。

## 3. `8cb1b4929` RE06：同意门锁内复核（TOCTOU）
门在锁外读台账，到抢锁之间 API 侧可追加撤回，老实现不复核就写，**修复前实测真写
出了 run_started**。改为在 `try_transaction` 内复核同一谓词（读 txn；锁外再读一遍只是
缩小窗口，变异 T2 专守此伪修法）。锁外那道门保留：本就不该写的不去抢锁。
**时间语义不变**：按事件自身时刻判定；改写时语义会凭写入延迟丢事件。

## 4. 计时按钮与测量门耦合（现状刻画，待你定口径）
前端 `ResearchActivityControl` 在停止/切会话/`pagehide` 发的 withdraw 记在 owner 名下，
用的又是测量门那组 scope，故**停一次计时 = 自用测量永久关停**，界面却只说
「研究功能不受影响」。已补门页与刻画测试。
三条路：改文案 / 计时同意换独立 scope 名 / 门忽略该 `consent_version`。推荐第二条，
但它改 05 读数，须你定。

## 未做 / 边界
- **跑全量前先看 `uptime`**：本机常有十几棵树并发跑 pytest（实测 load≈80、17 个进程）。`test_rag_worker::test_warm_worker_survives_first_timeout_...` 会因此
  假红——同一提交 `8975ce0f2` 两次全量一红一绿，别去「修」它。
- 作者自验，非独立 QC；P7 隔离验收（新会话+原始 T3+真实模型）未做。
- 未编号的本地多问题仍落 `direct_answer` 一格。切题是 `user_task.py` 的**确定性正则**，
  无模型参与；扩到无编号等于改信任模型，属产品判断。

## 已验证
- TOCTOU 同族已筛：17 处事务只此一例。`fold_run_terminal` 是正例（决策态锁内
  读）；`create_binding` 的锁外预检只是快路径，幂等在锁内。
- 新测试四份（E2 20、折叠 18、TOCTOU 6、计时门 5）；变异 7/7、8/8、5/5 全杀。
- 回归：RE06 十一套 186P；全量 10630P / 23S / 2X（含上述假红）。
