# docs/closeout-workorders-0922

## 这个分支做什么
#73/#75本地合并部署就绪。入口`docs/verification/2026-09-24-re06-current-main-readiness/README.md`；快照`docs/handoffs/2026-09-24-re06-current-main-resource-block.md`。

## 决策与被否方案
- B不变：计时scope/v2与测量分离；旧v1窄读取兼容，不迁移。
- 旧7ec过时，完整b24合到当前main；INDEX冲突保留main，其余与merge-tree一致。不移签旧绿。
- 与7ec的intelligence有4文件差分，已撤销“全子树相同”前提。
- 两调度器共用15分钟资源窗口，已结束；不无限轮询、不停别人任务。

## 当前状态
代码`b027194f1039692b8c26cacf9310619d633c54b7`，base`3bb81b9638f97b4773ce0f338df3a505b7c0162f`；作者`~/fwp-wt-re06-ready-current-0924`。R=`~/.finance-runtime/reviews/re06-deploy-readiness-20260923-01`；独审`R/qc-k3-04/candidate/finance-workspace-private`，两树clean，收尾fetch漂移0。
NOT_READY/BLOCKED_RESOURCE_GATE。测试/build/真实模型0；acceptance-05仅备runner，无执行receipt。PID3166/13220结束，30001/30004无监听，无自动续跑。未push/PR/合main/部署/生产写入/改8792/删树。

## 已验证
宿主沙箱/命令边界、18事务点枚举、14变更Python语法和发布资产引用通过，均不签语义。新runner超时complete=true用宿主夹具验证；旧失败保留。清理约6.6GiB通过pytest临时夹具，旧拒收/日志/收据不变。旧1251原件复验，新139原件归档。

## 未验证 / 已知边界
C1-C10全not_verified，Quality/自然质量未评估；实际执行预检/gateway/三组独审/四叶未跑。旧8eac E2独立19P/作者20P/正控1F与PASS_WITH_LIMITS仅历史，不移签。
readiness147/218请求、余71、计划另69；shipping73另账。K3/xhigh，重试0，218是宿主上限。#76各行与P7 A1-A17另协议/授权，仍禁正式T2/T3/Knevo对照。#68/#71/#66未推进，#69仍绑3b7e473575b0。

## 下一步
1. 先协调资源窗口并fetch验漂移；门槛load<=8、预计pytest<=2、空盘>=8GiB；工程启动额外留12GiB。
2. 新状态/日志路径恢复，别重跑已结束controller。冻结依赖、实际预检、gateway、三段独审与新四叶，作者/独立分账，完整SHA/全量/base-drift-max5。
3. 本地有界就绪工作仍已授权；发布/生产与自然质量另授权。

## 踩过的坑
模拟预检也生成请求账，不能无范围glob计真实请求；新QC预检文件名不要猜。两次宿主收尾失败保留。封存后dry-run仍追加日志，已另存全记录并恢复封存字节；以后仅无写入观察。默认users隔离要覆盖conftest清环境后的回退。一次性脚本绑定本机/预算，未晋升通用工具。
