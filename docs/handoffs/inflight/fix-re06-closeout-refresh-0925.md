# RE06 独审拒收在途

## 这个分支做什么
#73固定a30e7e4594ac/base03352758c的本地有界工程/独审。R=`~/.finance-runtime/reviews/pi-closeout-execution-20260924/re06-a30e-locked`，Q=`R/qc-execution-final-06`。文档/工具提交不移签候选。

## 当前状态
09-25 17:35+0800：执行预检PASS，gateway2请求PASS；e2 execute3请求，阳性对照被资源拒绝exit75后，模型用write把自身执行收据覆盖成占位文字。仅终止本任务PID/组48820，runner记录BLOCKED、无终稿；已退出无后台。reviewer/author未执行。新增5请求，累计186/218余32。原件不恢复，本批不再用。详见`2026-09-25-re06-qc06-receipt-write-rejection.md`及R/qc06-integrity-audit-0925/incident.json。

## 决策与被否方案
收据损坏即拒收，不续模型补报告；不按marker伪造恢复原件。文件工具改组/阶段允许清单，探针create-only，不只提示勿写。任意探针仍需独立OS写权限，不把helper绿当全链闭合。

## 未验证 / 已知边界
新review_artifact_writer.py仅离线验，尚未接入新批次。旧file_tool和sandbox都允许写整个work，探针子进程仍可能写其他收据。三组独审/C1-C10/C2语义路径与#76自然验收仍缺。main64847b7a1正式漂移54>5拒收，a30e工程绿不能用于当前合入。未push/PR/合main/生产，不接管邻线。

## 下一步
先R/inspect_status.py核账。禁止重跑final06/重复prepare。接入新文件写入器，并分离模型产物与宿主证据的OS写权限；实跑越权反例后重新规划余32请求，不能沿用原37计划或自动加预算/重试。固定候选审查与新main组合工程各自准入。

## 踩过的坑
工具交付不等于测试过；完整预检PASS也只覆盖已测路径。收据在work可写根内不算不可变；chmod文件不防可写父目录替换。原marker hash42f28d10仅证原字节曾存在，不是备份。check_execution实际JSONDecodeError/exit1，不是有效执行检查PASS。原文件保留现场。

## 已验证
候选a30e锁定Python3.12.13/httpx0.28.1/Node22工程15470P/86S/2X、前端122P/E2E34P2S、registry五项0。此次预检Python5P1预期F/UI1P1预期F、作者仅收集109；非业务独审。新writer标准库unittest13项及Ruff通过，含真实临时CLI/撤保护覆盖/软硬链接，0新pytest或模型；日志在事件审计目录。
