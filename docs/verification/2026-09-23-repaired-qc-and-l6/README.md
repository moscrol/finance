# PR #868 三项修复后的新验证批

## 结论

**仍然 WIP，不能合入。** 产品候选 `ac11027fa75ee6a988ab90ab81e0329159964643`，基线 `626d8a508c1c988ff094110b371987e6afdcdd15`。本轮未 push、未合主干、未部署，也未续跑或改判历史失败批。

- #75：独立 Spec 交付 `PASS_WITH_LIMITS`，Quality 交付 `BLOCKED_INCOMPLETE_EVIDENCE`；宿主验收状态为 `BLOCKED_INCOMPLETE_INDEPENDENT_EVIDENCE`，不是宿主代签的独审 verdict。
- #76：新 L6 在两项准入预检处停止，`BLOCKED_PREFLIGHT`；三题均未提交，自然质量 `NOT_EXERCISED`。历史 L6 `NOT_PASSED` 保留。
- 当前候选的完整工程门禁和最新 main 联合树门禁未跑。328 项定向通过不能替代它们；`merge-tree` 无冲突也不能替代联合测试。

## 已落地的修复

1. `episode_semantic_verifier.py` 仅对明确成交额/市值货币字段解析单位，用 Decimal 换算，保留合理显示舍入；拒绝未知字段、股数、错误量级及未绑定证据。旧 Episode 原件的 `成交额元=11226516458.33` 能支持 `112.27亿元`；改成成交股数后拒绝，还原后再次通过。原件 SHA256 不变，无网络/模型调用。
2. `pi_review_protocol.mjs` 的 `bindStageResult` 由控制器绑定 stage/axis/revision/baseline；模型只提交内容，身份注入即使碰巧一致也拒绝。新批六个正式阶段均有效交付，没有重现旧批大小写身份错误。
3. `adaptive_l6_batch.py` 将精确 Episode 的 source audit PASS 设为下一题的必要准入条件；缺失、异常、超时、错误 hash、malformed、非 PASS 或运行未完成均停止。真实回环假服务覆盖失败后下一题请求为 0 和 PASS 可继续；本批预检即停，没有自然触发该屏障的证据。

作者定向收据 [test-receipt.json](offline/test-receipt.json) 为 **328 passed / 0 failed**，来自干净候选，`check_test_receipt.py --expect-revision ac11027fa...` 校验可采信。目标为 semantic verifier、review protocol、L6 audit 三个测试文件，包含真实 pi CLI 离线协议测试，不是完整套件。作者全仓 Ruff 与 `git diff --check` 通过。

## 独立审查

模型 `glm-5.3`，官方 Coding 端点；没有关闭服务端 thinking 的声明。每轴独立 explore/execute/report，会话不共享另一轴结论。阶段最多 24 请求、单请求 120 秒、阶段 600 秒，正常请求 16 次或 420 秒触发一次保留收口；自动重试 0、没有扩预算。网关准入每轴最多 4 请求。

| 轴 | Gateway | Explore | Execute | Report | 合计 | 原始 verdict |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Spec | 4 | 12 | 17 | 1 | 34 | PASS_WITH_LIMITS |
| Quality | 4 | 9 | 17 | 1 | 31 | BLOCKED_INCOMPLETE_EVIDENCE |

合计 **65** 次，shim 与控制器计数相符，active=0，shutdown_complete=true。报告包只含同轴交付、探针原件和工具输出，不含模型思考或另一轴结论。

- Spec：[原始终稿](qc/spec/report/submission.json)。C3/C5/C6 not_verified；C2 只行为拦截四个 HTTP 调用点。作者测试 0；探针按脚本调用记 **1 passed / 3 failed**，失败包含探针判定及 API 签名错误。必红对照未跑。
- Quality：[原始终稿](qc/quality/report/submission.json)。C1-C5 not_verified。作者测试 0；实际运行一个 transport 脚本，其六个子项 **5 passed / 1 failed**，该脚本整体 exit 0，不能把退出码当六项全过。取消子项收到 HTTPDeadlineExceeded 而非预期异常，模型未裁决是探针问题还是产品缺陷；findings 为空不等于正确性已确认。refine/judge 探针与必红对照未跑。
- 两轴的探针分母不同，不相加为一个测试通过数。作者的 328 项也不计入 reviewer 的作者测试栏。
- 宿主没有修正模型报告的 verified 标签、补跑缺项后代签，或把 `PASS_WITH_LIMITS` 升格为 C1-C7 全部通过。三项新修复的独立正确性覆盖也未完整闭合。

冻结依据是 [authorization.json](qc/authorization.json)：它在新候选、主张及源索引固定之后、所有模型请求之前生成。`repair-inputs.json` 是更早的未授权模板准备收据，不是本批最终冻结清单。授权清单全部哈希保持不变，候选审查前后干净。

## L6 准入阻塞

新根 `~/.finance-runtime/reviews/pr868-l6-repaired-20260923-2118/`，三道新题是中际旭创可证伪跟踪、生益科技本地量价比较、液冷服务器发酵阶段。题目、预算、根均独立于历史失败批。

1. [strict-deadline.json](l6/strict-deadline.json)：13 个场景中 body_stall 越窗。输入 0.8 秒，调度容差 0.2 秒，实测 1.378275 秒；端点实际收到 **0** 次 HTTP 请求，attempt 处于 open_response，worker returncode=-9。因此没有走到响应体停滞测试目标，但墙钟门依然红。采样机器 1 分钟负载 60.27 只作背景，不能据此判为环境误报，更不能放宽窗口重跑覆盖红收据。
2. [retrieval-probe.json](l6/preparation/retrieval-probe.json)：本地模型权重存在，离线就绪检查 120 秒超时，exit 124；日志为空，无下载、无付费模型请求。没有证明具体是初始化、调度或其他依赖故障。

代理离线检查 PASS 和原件金额回放 PASS 不抵消以上红灯。实际首发 **0/0/0**，重发/续问 0，真实金融模型请求 0，旁车启动 0。没有新 Episode、source audit、真实修订或自然迟到判官结果。

整库快照使用 `market_feature_store.db.clone_to_staging` 的 clonefile 路径，独立 inode、SHA256 一致；751 个冻结文件复核不变，生产七项身份不变，无锁获得。19897/19898 空闲，19899 的 QC 代理也已释放。

## 归档与边界

- [宿主汇总](qc/report.json)、[L6 收口](l6/report.json)、[合入预览](qc/merge-check.json)、[原件清单](archive-manifest.json)。本次复制 499 份文件并逐份比对 SHA256，密钥扫描 PASS。模型事件/响应原件留私有目录，不将思考文本放入仓内报告。
- 旧 #75 的 36 请求交付失败、旧 L6 的 20 请求与误删失败维持原判；旧原件只读用于回放和数据快照。
- 开发分支已前向吸收上述 main；当前 revision 完整 Python/前端/E2E/registry 与联合门禁无结论，不借用 `7ad61a0d3` 的历史全量收据。
- 已清理本轮干净候选检出和通过测试 basetemp，日志/收据及失败批数据保留，见 [清理收据](candidate-cleanup.json)。检出路径现已不存在，可按固定 SHA 重建，不得在旧批续跑。
- PR #868 评论6498、#852评论6500已逐字回读；PR标题仍WIP并明确双重阻塞，未关闭。标题写请求超时但只读回查确认已生效，未重复发帖。pull详情及ls-remote读超时，未重新认证远端head；本轮未请求任何代码写入。见 [状态回读](gitea-status.json)。
- 下一轮先解决完整独立覆盖与本地准入阻塞，再用全新受限批次；不得续跑此批、补旧题、调大预算或重写任何原始交付。
