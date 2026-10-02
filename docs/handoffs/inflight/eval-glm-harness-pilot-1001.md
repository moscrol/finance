# eval/glm-harness-pilot-1001

- 用户最新决定：先用GLM实跑找harness局限；不等Claude，不把ReAct必胜作为前提。
- 本分支基于PR11 d177a940e，只改实验文档/台账/合成夹具；draft PR12 base=fix/qc-closeout-1001。不合main、不部署、不跑240。
- R-20261001-08已原子领号、先提交推送事前协议，再跑模型；现仅就实验验收confirmed，非缺陷修复confirmed。
- 实际代码固定d177，模型glm-5.3。P用真实create_app对话API（隔离ASGI，无UI，不是核心Episode冒充产品）；R用薄ReAct。同只读库、相同问题/外部上限；原生工具菜单/合同/内层预算差异明示。
- 两题×两流程均completed，HTTP及原生模型准入均0。S1 P/R数值槽3/3、3/3，3/2物理请求，21.613/11.244s；S2 P/R8/8、8/8，2/2请求，19.856/11.105s。人工核对日期/公式/出处正确，不作普遍胜负结论。
- 已证实优先问题：S2“不要推测市场涨跌原因”被编译成market_cause，强制causal_chain/counterpoint/cause_attribution。GLM仍答对数值但处理了多余因果合同。零调用六变体复放：3个否定输入错误、3个无该句/正向/双重否定控制正常。尚未修复；合成夹具已入Git，不能用单题专属正则蒙混。
- 可选记忆槽候选未得到因果支持：原S1多查一次空记忆；固定第二轮请求后原样控制与删prime_memory都直接stop，无工具，身份均0。原样未复现，不删生产记忆，不称提速。
- 本轮共11物理模型请求（9对照+2检查点）。v1错误backend枚举glm在create_app阶段0调用失败；v2先改continuous_glm、重新冻结再调用，旧原件保留。
- 私有证据：~/.finance-runtime/glm-harness-pilot-20261001/ 下v2、checkpoint-memory、negation-replay.json、postcheck.json。原始模型答卷/凭据/3.6GB库不入Git。
- 并行收口：d177 Mac规范全量18,993P/75S/2xfail、full-scope19,070核对通过；GitHub五绿；真实队列前后7385行/hash一致。严格AB仍966/955/11 exit2，11份不适用口径未批准；PR11仍draft。
- 最新复核main3a2718c6c、生产8792 healthy/2c3949786568/code_matches_repo=true，快照和真实队列hash未变。
- 下一步优先否定意图/合同编译边界：共享语义方案→六夹具与更广正反例→同GLM同库完整产品复跑原S2及正向/双重否定控制。不要先改预算、重试或记忆。
- 详细报告：docs/verification/2026-10-01-glm-harness-pilot.md。
