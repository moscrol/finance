# PR884 对齐新主干后的候选冻结

## 授权与背景

用户在上一轮结果后说“执行”，承接的是“针对最新main固定新的合并候选并复验”。不解释成合并、部署或追加K3授权。

上一轮c71e3c8221be的本机完整命令检查已通过，但运行期间main合入#856，前进到27ca084f9ffcb9d148b749944beca340e5f4fa6c。旧收据不能证明这个组合。Python当轮1428.039秒，也未证明workflow的900秒时限。

## 已完成的对齐

- 主检出树有他人改动；继续使用干净的fwp-wt-runtime-postmerge-qc-0923。
- fetch后核对#884仍open/WIP、head为c71；当前main固定为27ca。
- gitea_pr.py conflict-check预览clean，tree为cfea017d2bc8dd024534dd1d9b6c4420814133c1。
- 仅把main合入本分支，生成9e82314a412902901e5048a04a9459bc582fdafc；双亲和树与预览一致。没有向main合入。
- 相对新base的intelligence/market_feature_store差异仍只有intelligence/tests/test_episode_writer.py，没有新增运行时产品改动。

本文件与inflight在新轮门禁前提交。后续冻结的完整SHA由树外运行配置记录；最终读数不再通过追加文档提交改变已测head。

## 执行选择

| 方案 | 评价 | 决定 |
| --- | --- | --- |
| 沿用c71旧绿 | 不能覆盖新主干组合 | 拒绝 |
| 只跑#856相关用例 | 不能代替完整合流门禁 | 拒绝 |
| 给整个pytest套额外Seatbelt | 上轮同例对照已证明会干扰系统沙箱和RSS自测 | 拒绝 |
| 原生Python完整门禁，逐叶记录环境 | 保留测试自身防护与完整分母 | 采用 |
| 改workflow超时凑绿 | 未证明CI机器需要扩时，也超出此次对齐范围 | 拒绝 |
| 依次注册表、前端/E2E、Python | 本机已有其他全量任务，减少自身并发负载 | 采用 |

仍使用仓内run_main_gate.sh与run_frontend_gate.py、指定Python解释器和Node22工具链。Python执行环境清空凭证、关闭LLM钥匙串、使用独立用户目录，但不宣称全轮OS禁网。Codex系统隔离测试不调用模型。其他叶子在外层策略运行前做真实动态预检。

本机完整Python监督上限1800秒；workflow 900秒另列实际是否达到，不偷换两者。记录耗时分布以供后续定位，不从单轮差异宣称性能改善。磁盘不足则中止本轮且保留失败，不删除其他任务现场。

## 最终证据与边界

新目录：`~/.finance-runtime/reviews/pr884-gates-20260923-03/`。最终结论只读其中verification.json及#884最新门禁评论；缺失即未完成。初末Git身份、日志哈希、pytest完整收集面、实际head/base和merge-tree均需核对。旧-01/-02目录及仓内原始归档不改写。

历史C1-C8独审保持BLOCKED，宿主工程检查不替代独立动态验收。完整跨进程driver、跨机锁、真实费用对账及生产金融问答等旧边界仍未覆盖。

完成后只清理由本轮新建、干净且无运行进程的临时代码副本；保留失败原件和收据。不撤WIP、不合并、不部署、不继续K3。若main再次变化，明确记录新组合未验，不移签收据。
