# RE06 QC08 控制夹具拒绝在途

## 这个分支做什么
#73固定a30e7e4594ac/base03352758c的本地工程/独审。R=`~/.finance-runtime/reviews/pi-closeout-execution-20260924/re06-a30e-locked`，Q=`R/qc-evidence-isolated-08`。工具修补不改变产品候选。

## 当前状态
09-25续推：QC08已接用户目录修补并冻结。23:51真实pytest收集10例，8P/2F/exit1、有JUnit；额外失败是evidence/e2父目录缺失导致FileNotFoundError，不是预期权限拒绝。失败即停，UI/作者收集/gateway/E2未启动，无动态重试/后台。0新模型，186/218余32。夹具准备helper/507件归档已提交7434a38a1，未接下一批。快照`2026-09-25-re06-qc08-controller-fixture.md`。

## 决策与被否方案
不把缺目录算权限拒绝，不改预期为8P/2F，不在失败Q08内补目录重跑。新prepare_evidence_groups只建全新evidence及四组父目录，旧树拒绝；下批冻结前接线。保留QC06/07/08原件。E2最多11新请求，timer/consent仍未准入。

## 未验证 / 已知边界
新夹具helper仅作者离线验证，完整Python/UI预检仍未过。三组C1-C10、C2语义、timer C7、consent C6、#76自然验收欠缺。本轮未固定/验新main，旧工程绿不移签。不push/PR/合main/部署，不接管邻线。

## 下一步
先R/inspect_status.py核账（已补新批次计数，原版另存）。准备全新批次时复制最新review_io_sandbox.py及qc_userspace_isolation.py；用prepare_evidence_groups(new_Q/'evidence')替代裸evidence.mkdir，在冻结前调用，不对旧Q执行。重新绑定源码/路径/探索输入；资源准入后真实控制预检，成功才gateway→E2 execute→事实核验→report；拒绝即停。Python用R/candidate/.venv-workbench/bin/python。不要重跑prepare_qc08或原预检/归档器。

## 踩过的坑
缺目录使权限反例先报ENOENT，不能算权限机制通过。故意失败必须核具体失败身份/JUnit，不只exit1。原RUNNING保留，host-step/incident另给终态。测试discover须指定本树顶层或cwd，主检出缺本枝review_probes。

## 已验证
QC08离线13项命令检查含36P/9组SDK写边界通过；新修补后39项unittest/Ruff过，删父目录反例红。507件源/归档/7434a38a1 Git blob全等。真实插件已到收集，候选树干净；预算临时台账验证新批计入、离线夹具不计、错序拒收。历史a30e工程只签旧候选。
