# RE06 锁定候选在途

## 这个分支做什么
承接#73本地工程/独审。固定a30e7e4594ac（base03352758c）；文档提交不移签。R=`~/.finance-runtime/reviews/pi-closeout-execution-20260924/re06-a30e-locked`，Q=`R/qc-execution-final-06`。

## 当前状态
09-25 12:04+0800：本轮0模型，实际181/218余37，无本任务后台。首次资源准入后，11:50执行边界被load13.35/pytest3预计4拒绝exit75；不重试/不杀外部任务。final06未启gateway。e2已prepare-only冻结准入；修冻结目录复用、当前工具清单、typed提示和Pi非零exit异常分流，原探针断言不动。详见`2026-09-25-re06-controller-alignment-and-drift.md`及Q/continuation-0925.json。

## 决策与被否方案
复用原探针另绑当前工具，不覆盖原manifest。对照失败按原exit/收据分类，不全局吞异常。资源拒绝停，不自动等。主干漂移不调阈值、不移签。

## 未验证 / 已知边界
新版控制器仅离线通过，真实沙箱执行边界未过；三组独审/C1-C10及C2语义判官缺覆盖，作者测试不能补签。#76自然验收与发布另授权。末核main79861f07e；正式合并漂移27>5，exit1，旧工程绿不能作当前合入门禁。未push/PR/合main/生产；不接管#61/#868/#884。

## 下一步
用户续推后先跑R/inspect_status.py并查资源。人工运行Q/execution_boundary_preflight_v3.py，全PASS才gateway最多2。e2已冻结，不再stage_admission重复创建：run_stage_v3.py execute e2，然后check_execution_v3.py e2；失败即停。其余探索/执行/报告串行。需合入时另固定新main组合和全门，不能更改当前冻结身份。

## 踩过的坑
Pi实际CLI=/opt/homebrew/bin/pi；Q无独立pi。run_probe baseline首个调用，禁止bash；故意失败exit1不是工具链失败，实际exit/marker/hash须一致。原manifest属旧探索，execution-manifest属当前包装器。preparation写6终稿有误，实际8，阶段总35+gateway2恰余37。新版离线收据带0925，旧PASS不继承；失败原件保留。

## 已验证
固定锁定环境Python3.12.13/httpx0.28.1/Node22：15470P/86S/2X、15558收集、真实exit0；前端122P/E2E34P2S、registry五项0。唯一pytest收据R/receipts/gate-a2kwxg5I/pytest.json。本轮身份/环境/范围一致，唯漂移拒收。菜单/工件/边界及真实SDK模拟exit0/1/75/127离线PASS，0pytest/模型，不是独审。
