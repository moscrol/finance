# RE06 QC07 写隔离在途

## 这个分支做什么
#73固定a30e7e4594ac/base03352758c的本地有界工程/独审。R=`~/.finance-runtime/reviews/pi-closeout-execution-20260924/re06-a30e-locked`，新Q=`R/qc-evidence-isolated-07`。产品候选不变，工具/文档提交不移签。

## 当前状态
09-25 18:51：新写边界已接Q07，25项unittest/Ruff、9组真实SDK文件工具及原生探针越权反例通过；只证离线IO边界。18:41资源pytest3预计4拒绝exit75，本轮0pytest/0模型、无等待重试。实际仍186/218余32；Q07 gateway/execute/report未启动，无后台。原QC06损坏与incident所列文件哈希未变。详见`2026-09-25-re06-qc07-write-boundary.md`；482件原件及清单在同名evidence目录。

## 决策与被否方案
模型只写本阶段交付/新探针，探针只写本次scratch，宿主evidence分开；不靠提示词/chmod保护收据。JUnit宿主退出后取证，拒链接/FIFO/大输出。保留Q06，不恢复坏JSON。Q07先限E2切片最多11新请求，不沿用旧37计划；timer/consent未获本切片准入。

## 未验证 / 已知边界
实际pytest/UI包装器预检尚未运行，不能把原生Python越权反例当全链通过。三组独审/C1-C10/C2语义判官、#76自然验收仍缺。旧main64847正式漂移54>5拒收，本轮未重签新main。未push/PR/合main/部署、不接管邻线。

## 下一步
先R/inspect_status.py核账。新准入后依次Q/execution_boundary_preflight_v3.py → run_gateway.py → run_stage_v3.py execute e2 → check_execution_v3.py e2 → stage_admission_v3.py report e2；任一步拒绝即停。Python用R/candidate/.venv-workbench/bin/python。E2 manifest已prepare，不重跑stage_admission execute/prepare_qc07。通过后再按剩余额度规划另外两组；要合入另固定新main组合验工程。

## 踩过的坑
tools-v3.sb只是旧写策略模板，不能直接用于探针。模型工件绿不等于实际执行。任何绑定工具改动都须新预检，不改旧hash刷绿。offline-validation/receipt.json的RUNNING是记录器断言失败遗留：stage实际先被缺gateway挡住；正确核对在offline-validation-completion.json，原件未改。

## 已验证
Q07候选/作者树干净；离线收据均核哈希，gateway/execute因缺前置收据拒绝且未取凭据。锁定Python3.12.13/httpx0.28.1。历史a30e工程15470P/86S/2X、前端122P/E2E34P2S、registry五项0只签旧候选，不补本轮独审。
