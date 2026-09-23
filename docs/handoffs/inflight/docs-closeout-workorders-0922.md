# docs/closeout-workorders-0922

## 这个分支做什么
维护工单；当前#73/#75就绪续跑。入口`docs/verification/2026-09-23-re06-deploy-readiness/README.md`；决策快照`docs/handoffs/2026-09-23-re06-readiness-refresh-and-resource-block.md`。

## 决策与被否方案
- B不变：计时独立scope/v2，旧v1窄读取兼容，不迁移。
- 旧8eac全量绿但基座漂移15超上限5，另建7ec固定合流，否决豁免/移签。
- 资源检查在可信wrapper，测试仍沙箱；只开目录元数据，默认users根也隔离。
- 两条有界等待结束即停，不无限重跑，不结束别人任务。

## 当前状态
本地代码`7ec9d022b14db46ac667accc08c7891f27f5a1a6`，base`626d8a508c1c988ff094110b371987e6afdcdd15`；作者`~/fwp-wt-re06-ready-refresh-0923`。R=`~/.finance-runtime/reviews/re06-deploy-readiness-20260923-01`；独审`R/qc-k3-03/candidate/finance-workspace-private`，两树clean。
NOT_READY/BLOCKED_RESOURCE_GATE；新候选测试/build/模型请求0，acceptance-05未创建。所属进程结束，29801/29804/29901/29904无监听，无自动续跑。未push/PR/合并/部署/生产写入/改8792/删树；证据随本次文档收尾保存。

## 已验证
历史b24四叶PASS；旧8eac pytest14726P/85S/2X、其他三叶绿，但完整收据因漂移拒收。旧QC02 v3 E2正控1预期F、独立19P、作者20P，C1-C3 verified、Quality PASS_WITH_LIMITS，仅限旧版。
新QC03只过宿主沙箱/命令边界及18事务点枚举，不是语义批准。两版intelligence树相同仅支持差分探索。归档原字节/请求账核验见入口verification.json。

## 未验证 / 已知边界
当前C1-C10全not_verified、Quality未评估；三组探针重定位待接纳，实际执行预检/gateway未跑。timer动态UI、consent独立事务分类/执行/报告仍缺。
readiness累计147/218请求、余71，旧shipping73另账；K3/xhigh，自动重试0。218是宿主上限非用户原话。#76六行与P7 A1-A17另行协议/授权，禁止正式T2→T3/Knevo对照。
#68/#71/#66未推进；#69仍绑3b7e473575b0，共享脏主树未改。

## 下一步
1. 先查资源并fetch验漂移，再用新状态/输出路径恢复；不覆写已结束控制器。必要时新固定合流，不继承结论。
2. 准入后冻结依赖/实际预检/gateway，三组explore→execute→report及新四叶；作者/审查者分账，Python完整范围与base-drift-max5。
3. 本地有界QC仍在本次授权内；勿沿用旧交接的“未授权继续”。自然质量与发布/生产动作仍另授权。

## 踩过的坑
conftest会清环境，仅设users环境变量不足。正控能跑不代表作者收集能跑。acceptance-04旧complete假值由closure解释，不改原件。一次性脚本固定本机/白名单，未晋升通用工具；宿主PASS不代独审。项目记忆原已脏，仅定点回写、不提交整文件。
