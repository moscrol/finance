# RE06 QC07 执行器拒绝在途

## 这个分支做什么
#73固定a30e7e4594ac/base03352758c的本地工程/独审。R=`~/.finance-runtime/reviews/pi-closeout-execution-20260924/re06-a30e-locked`，Q=`R/qc-evidence-isolated-07`。工具修补不改变产品候选。

## 当前状态
09-25 23:23：真实预检已启动且失败，不再只是资源阻塞。已有pytest1预计2获准，插件仍检查work而执行器传scratch/users，加载期exit1、counts=null、无JUnit；上层原收据留RUNNING。UI/gateway/E2未启动，无自动重试/本任务后台。0新模型，仍186/218余32。修补模板与16件证据已提交46e094bc0，未接入Q07。详见`2026-09-25-re06-qc07-userspace-rejection.md`。

## 决策与被否方案
保留Q06/Q07原件，新模板等新批冻结前接线；不删目录检查、不原地改manifest刷绿。模型工件/探针scratch/宿主evidence分开，JUnit由宿主取证。E2最多11新请求边界不变，timer/consent未获切片准入。

## 未验证 / 已知边界
新插件尚未经真实pytest/UI包装器验证；离线导入/消费者回归不代独审。三组C1-C10、C2语义、timer C7、consent C6及#76自然验收欠缺。旧main64847漂移54>5只是旧观察，本轮未固定新main。不push/PR/合main/部署、不接管邻线。

## 下一步
先R/inspect_status.py核账。准备全新批次时将`scripts/review_probes/qc_userspace_isolation.py`复制到新inputs，再绑定新路径/源码/冻结输入；不能续跑旧Q预检或重跑prepare_qc07。先真实执行器预检，成功才gateway→E2 execute→事实核验→report；任一步拒绝即停。Python用R/candidate/.venv-workbench/bin/python。合入另固定最新main组合验工程。

## 踩过的坑
exit1可能是加载失败，不等于预期1F；必须有collected与JUnit。原RUNNING保留，新incident给终态。旧482件归档没变，但对应资源源台账合法追加506字节，其余481源未变；不要拿旧manifest验证追加后台账再误判篡改。

## 已验证
新插件11项加旧writer/OS隔离共36项unittest/Ruff通过，含恢复旧work检查后合法路径被拒。16件源/归档/46e094bc0 Git blob全等。新模板未覆盖Q07。候选树干净，历史a30e工程15470P/86S/2X、前端122P/E2E34P2S只签旧候选。
