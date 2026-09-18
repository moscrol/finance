## 这个分支做什么
复用Workbench/Episode/history_query与主库，完成市场参照→强势对象→启动/峰值→接力→同口径特征。

## 决策与被否方案
| 选 / 否 / 理由 |
|---|
| 可信用户链+三类时间合同 / 助手旧答授权 / 防续问扩权 |
| typed诊断+清洗，事实照常过门 / 空evidence或error放行prose / 防事实洗入 |
| market错参明确反馈 / 按代码暗推类型 / 不替模型改对象 |
| 保留红收据再冻新SHA / 局部绿抵全量或重跑挑成功 / 分清证明层 |
展开：`docs/handoffs/2026-09-18-history-diagnostic-repair.md`。

## 当前状态
独立树`~/fwp-wt-history-market-anatomy`。运行修复a05b3483；58b78542修遥测测试对照，固定四叶已完成。归档9527826c已推，WIP #783已更新；未合未部署。无后台待验，未改生产行情库/画像/每日链。
诊断被日期门吞、market漏类型反馈已做确定性修复，但没重跑真模型。最近fbd8四题整组仍失败。MOC/能力图谱9c55b9ce；harness探针登记de8c93c已推未合，共享BUILD未碰。

## 已验证
58b固定clean：Ruff、Python11531P/81S/2X、前端107P及lint/typecheck/build、浏览器34P/2S、registry五项0（98warning）；pytest收据八项过。两条脚本Episode纠错链+四个进程内变异通过；只证明接线，不证明自主研究。
`docs/verification/history-market-anatomy/58b78542/acceptance.md`索引19份哈希核验归档，含a05全量两红与变异故意失败；旧fbd8真模型原答未覆盖。

## 未验证 / 已知边界
真模型纠错未复验；接力immature误读、异窗rank、前向偏题、启动特征/控制组仍未修。旧四轮必答仅直接判断/反证/证据边界，第四轮另有可选近5日量能项，只是线索非根因证明。
analogues排序未独立复算；无人员QC/浏览器真实研究交付/完整方法认证。首轮漏隔离EpisodeStore、第二轮缺health-after已披露。graph_audit退出0仍有PENDING/UNVERIFIED；vault_lint19错17警告。每日水位/代码根另案。

## 下一步
从已保存失败补接力状态投影→消费回归，再修同窗/启动特征合同与跨轮原件主动读取；不只加同一句提示。新代码另冻SHA跑四叶，业务片修完后新隔离根跑原四题，显式EpisodeStore；失败留档。合并/部署分别待授权。

## 踩过的坑
immature=源峰后不足5日，非失败；源峰无需先回撤确认，收益同源峰后5日。成员路径≠个股启动。volume_ratio是百分数，标签看专属source；cutoff非入库时点。遥测对照用独立task_id防缓存；脚本/算术/semantic绿不代业务，旧收据不代新SHA。
