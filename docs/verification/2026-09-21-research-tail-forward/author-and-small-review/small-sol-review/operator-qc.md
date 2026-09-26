# #831 根复核：接受固定候选的有限离线结论

受审源码 `ea5c3a94618a15e37f914c8b1a13e271875e4337`，基线 `f783f19c8a01fbe8d0ed70d851df7ed14598c051`。原报告 Spec/Quality 均 PASS；根复核接受为 **PASS_WITH_LIMITS**，只对 Timer 夹具归属与 code-map 有界别名两项离线合同成立。

- 这是一个独立 Codex / gpt-5.6-sol / 现有 ChatGPT 订阅 session 的两节报告，不是两位相互隔离的审核者，也不自称完全盲审。
- `events.jsonl` 首部实际返回受审HEAD与基线，session_facts指示干净；末部有最终报告及 `turn.completed`。外层未保存进程退出码，不能补造exit0。末次 `git rev-parse ...` 事件stdout为空，不能把原报告的身份文字当该条命令的返回；操作员随后独立回读审查检出仍为同HEAD、status空。前后抽样不能证明期间从未改后还原；完整events中的file_change只见仓外probe。
- 真实事件记录 `pytest` exit0：105 passed / 1 skipped，31.11秒，固定项目解释器、FWP_TEST_RECEIPT=0；Ruff exit0。现有回归包括三个真实夹具owner的“已从表移除但回调仍挂起”场景，以及别名总限额对照。
- 独立 `independent_probe.py` 最终 exit0。覆盖原查询与一次别名、两条结果去重、普通零命中、后端非零分类、无关Timer不被等待。它没有造足够多命中来压满限额；Timer在drain前已release，不能单独证明等待尚未完成的回调。**这两项强断言由上述现有正式测试的独立重跑支持，不冒称独立探针单独证明。** 原报告“探针覆盖限额/等待”的概括据此收窄。
- 探针首跑为脚本自身 else 后接 elif 的 SyntaxError；修正后重跑通过，原事件保留，不计产品缺陷。stderr末有模型目录刷新超时，但不推翻已经完成的报告与实际测试，也不当作源码错误。
- 未调用真实 code-review-graph 后端；未跑全量（作者全量另有准确收据）、未审#833/#834/#835领域功能、未验后来#830或联合组合、未部署。

旧host不可用/模型at capacity原件另保，恢复探针成功不是验收；此处只引用正式独立session的实际执行证据。没有授权合main，PASS_WITH_LIMITS不等于允许合并。
