### main12d 固定候选：定向与前端通过，全仓仍待准入

当前受测/发布 HEAD `2da72eef44787c910b5affbce47eea1e837ee7ae`，基座 `12d91dc733e1a29ceb54668fb934513bd10da4e9`。两边普通 merge 吸收 #933，无冲突，预览和实际 tree 一致，非强推发布。

- doctor、Ruff、registry 四项、crosswalk、整个 PR 源码 diff-check 全 exit 0。
- 沙箱作者定向 **74 passed / 0 failed / 0 error / 0 skipped**；精确版本与目标收据及续跑重验通过。C3 两轴各 3P、C7 各 66P 只属内层作者结果，不相加、不冒充独审。
- 前端六步全 exit 0，**123 单测通过，浏览器 34 通过 / 2 跳过**。初段端口绑定失败发生在执行前，原件保留；改独立端口续跑后通过，未重跑既有成功套件。
- 第03批轮到本 PR 全仓前资源拒绝，未启动。第04批仍固定此 HEAD，重新核验已封存原件与收据，只等待/补全仓，不借 #911 的通过数。

第03批归档已推协调分支提交 [`2b088cb3216d5e572740b2855fd2ed752a000ca3`](http://127.0.0.1:3300/a77/finance-workspace-private/commit/2b088cb3216d5e572740b2855fd2ed752a000ca3)，145 份选定原件全部入 Git，成员哈希 **147/147** 匹配。见 [范围与原件](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/2b088cb3216d5e572740b2855fd2ed752a000ca3/docs/verification/2026-09-25-pr910-main12d-gates03/README.md)。6 份前端日志（两 PR 各三份）结尾空行令协调归档格式检查 exit 2，已留非零回执，不改原件或宣称归档格式全绿。

main 后来前进到 `e159c564440c69abe17f106ae721fd25348a1865`（#932 数值预检），本候选未吸收；本批固定版本，不声称最新组合通过。原 PR inflight 是历史快照，本轮入口是协调分支 `docs/handoffs/inflight/baseline-pr868-current-0925.md`，第04批完成后再补结果。

WIP/open 保持。付费授权/模型请求 0；未独审、合 main、L6 或部署。作者工程验证不证明自然金融质量、真实来源、自主子研究、反证修订或 8792 身份，不恢复撤销批。
