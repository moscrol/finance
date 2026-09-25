### main12d 固定候选：离线工程门禁通过，非独审或合入许可

受测/发布 HEAD `34e31a25681868e26ddaaaf5d91854ec21be51ee`，基座 `12d91dc733e1a29ceb54668fb934513bd10da4e9`，无冲突普通 merge 吸收 #933，预览与实际 tree 一致。

- doctor、Ruff、registry 四项、crosswalk、整个 PR 源码 diff-check 全 exit 0。
- 两份研究链定向 **56 passed / 0 failed / 0 error / 0 skipped**，精确身份/目标收据与续跑重验通过。
- 前端六步全 exit 0，**123 单测通过；浏览器 34 通过 / 2 跳过**。两跳过是同一绑定流程仅 desktop 执行一份的既有设计。
- 完整 Python **16266 passed / 0 failed / 0 error / 75 skipped / 2 xfailed / 0 xpassed**，collected=16343。未传收窄范围参数，`--require-full-scope`、精确 revision/解释器/依赖、固定基座与零基座漂移检查全部通过。
- 按 PR 聚合 **PASS_NOT_INDEPENDENT_REVIEW**。定向与全仓不重复相加；75 skip、2 xfail 非通过。续跑批后来在 #910 全仓前资源拒绝，不改变本 PR 已执行的成功叶子，也不将结果借给 #910。

证据只写协调分支 [`2b088cb3216d5e572740b2855fd2ed752a000ca3`](http://127.0.0.1:3300/a77/finance-workspace-private/commit/2b088cb3216d5e572740b2855fd2ed752a000ca3)，不移动受测 HEAD。57 份选定原件中 56 入 Git，完整 JUnit 2.62 MB 外置原路径/大小/哈希；Git 成员哈希 **58/58** 匹配。见 [原件与范围](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/2b088cb3216d5e572740b2855fd2ed752a000ca3/docs/verification/2026-09-25-pr911-main12d-gates03/README.md)。原日志末尾空行导致协调归档格式检查非零，原字节和非零回执保留，不冒称归档格式全绿。

main 后来到 `e159c564440c69abe17f106ae721fd25348a1865`（#932 数值预检运行时变化），尚未吸收到本候选；这是固定候选通过，不是最新 main 集成通过。原 PR inflight 是历史快照，当前入口为协调分支 `docs/handoffs/inflight/baseline-pr868-current-0925.md`。

保持 WIP/open；付费授权/模型请求 0，未独审、合 main、L6 或部署。真实来源、自然金融质量、自主子研究、反证修订、8792 身份仍需各自证据，工程绿不替代它们。
