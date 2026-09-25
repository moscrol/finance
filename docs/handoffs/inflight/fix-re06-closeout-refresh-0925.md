# RE06 QC09 资源拒绝在途

## 这个分支做什么
#73固定a30e7e4594ac/base03352758c的本地工程/独审。R=`~/.finance-runtime/reviews/pi-closeout-execution-20260924/re06-a30e-locked`，Q=`R/qc-evidence-isolated-09`。工具修补不改变产品候选。

## 当前状态
09-26 00:51新Q09真实预检过：Python9P/1故意F，UI1P/1故意F，作者collect-only109（执行0）。00:52 gateway2请求过。00:53 E2启动前load1=8.974>8，exit75；E2目录/模型/探针均未启动，拒绝即停，无重试/后台。累计188/218余30；本切片11已用2，最多再9。529件归档e72745965源/归档/Git全等。快照`2026-09-26-re06-qc09-resource-refusal.md`。

## 决策与被否方案
不把控制/gateway通过算独审。不等待重试/抬阈值。新授权可在绑定不变时续同Q09，新宿主尝试收据保留本次拒绝，不重复gateway耗额度；源码/身份变则另批。Q06/07/08原件不动。timer/consent未准入。

## 未验证 / 已知边界
E2 execute/report和模型下收据完整性未验，三组C1-C10、C2语义、timer C7、consent C6、#76自然验收欠缺。未固定/验新main，旧工程绿不移签。不push/PR/合main/部署，不接管邻线。

## 下一步
先R/inspect_status.py核188及进程、候选干净a30e；复核Q内execution/IO预检source_sha256、冻结execution-manifest和gateway原件。用户重新准入后，用新宿主尝试路径调用同一run_stage_v3 execute e2；原run_qc09_step execute-e2目录已存在会拒绝，不覆盖或修改旧启动器/收据，不再次prepare/freeze/gateway。新资源准入成功才E2→check_execution_v3 e2→stage_admission_v3 report e2；任一拒绝即停。Python用R/candidate/.venv-workbench/bin/python。

## 踩过的坑
collect-only109不是109P；预期红须核失败身份/JUnit；exit75不是业务红。Q09新授权后资源台账可append，旧归档不变，以旧字节前缀验，不改旧manifest。QC08的缺父目录修补已在Q09实跑验证，不再是当前阻塞。

## 已验证
冻结前prepare_evidence_groups接线；离线13命令含39项unittest/9组SDK写边界过。真实三控制及2请求gateway过；候选树干净，原Q08的507件归档及源均未改。529件证据已提交，凭据元数据仅留本地hash。历史a30e工程只签旧候选。
