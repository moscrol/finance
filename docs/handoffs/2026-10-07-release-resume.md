# 恢复原任务：旧 PR 推送、准确版本验收与 #30 去留 — 2026-10-07

## 用户纠偏与当前目标

用户明确：「先把一开始交给你的任务做完，任务做完后我自己会让仓库私有。」
原任务是接手 PR / 发布核查、评估 main@ea21763 的独立审查、推进可靠回答与发布准备，
不是把中途事件处置扩成唯一主线。已通过既有 record-correction 入口记录具体纠正与原则。

授权恢复：已获准的分支同步、推送与自动化检查继续；可见性由用户随后自行处理。
风险单独记录，不能把“继续工作”写成“凭据已撤销/事件已结”。私有事件原件不上传。
每次合并、最终部署、写生产库和删除仍沿原约定单独确认。本页接续
[保护与临时暂停快照](2026-10-07-release-guard.md)，不改写当时的观察。

## 已执行动作（截至 10:25 +08）

1. 回读远端与协作评论：main仍 `ea217633ceeaceeb41d3b3f30fa58708fe14ecc9`；
   #49/#50/#51/#53旧head与冻结记录相同。#61/#62/#63/#66由其他会话推进，未抢改或代推。
2. 精确fetch所需分支，检查候选均包含旧远端head与准确main，不做rebase/强推。
3. 候选相对main的新增提交分别做默认Gitleaks脱敏扫描，均0命中；它不清除继承历史风险。
4. 10:10以一次 `git push --atomic` 普通快进推送四条PR分支；逐条回读精确匹配，main未改。
   atomic意为任一引用更新失败就整体拒绝，不是强推，也不构成合并许可。
5. main保护独立回读仍为strict、两项required checks绑定Actions、管理员受约束、禁强推/删除。
6. #51另在本会话新建的detached（固定版本、不跟随分支移动）独占树启动本机完整Python门禁；
   Ruff已过，pytest运行中，未声明通过。原定向收据仍单列，不移签。
7. 完成#30能力/消费者矩阵，并以真实函数做两端离线复验；源码和checkout身份前后稳定。

| PR | 已推送的准确 head | 本轮本机已有结论 |
|---|---|---|
| #50 | `570142a2498a6486cc1558b18982bf224cbc8d5e` | 仅3份文档增量；registry四项+crosswalk过，反向101 warnings |
| #51 | `a8fe098a83ddb6cd7e99004d24dbb20c6693c933` | 定向123P；完整Python门禁正在新树运行 |
| #49 | `a136e41e62bc20c1c9debfce0bf9901d309f2ff1` | 定向90P |
| #53 | `4594192cc5ba5a2706779b491b4be13a5c12b3b2` | 定向99P；仍以#49分支为base，未改main |

10:23观察四张PR的frontend/e2e/registry-check均成功，python尚在执行，不能称整体CI绿。
#53因堆叠base与head同次更新产生两组workflow；没有取消任一运行或择优挑绿。
每次合并前须再回读head、所有适用检查和最新main，不把本页时间快照当永久结论。

## #30 的已完成判断

正式对照：[PR #30 能力接替表](../verification/2026-10-07-pr30-capability-disposition.md)。

- #54改路由和资源上限，不等于替代模型计划撤回、输出来源、可选项履约、根请求/解释版本及模板建议化。
- 旧 `4cba44a63` 的TaskFrame前置ID去重未被#30运行时来源合流替代；build/rebase仍产生两个直接回答ID。
- 历史“只交证据边界但直接回答仍被判fulfilled”的反例，main与#30都复现；仍须独立处理，不能删测试换绿。
- 建议保留草稿，在运行时批稳定后按接缝重新合成/验收，不整枝盲合，不据#54直接关闭。
- 本轮没有自然模型收益结论；FINANCEWORKS-14已评论证据，未改任务状态或#30分支。

## 决策 / 备选 / 理由

| 采用 | 未采用 | 理由 |
|---|---|---|
| 恢复原发布准备，事件另记账 | 无限追加前置直到用户完成私有化 | 用户已明确优先级；不代替用户改任务范围，仍守住不上传新凭据的边界 |
| 准确head普通快进 + 原子四引用更新 | 强推或覆盖新远端提交 | 多agent协作，保留旧身份；漂移时停止对应动作，而非改写他人工作 |
| 定向→准确候选全量→最终main批次门禁 | 用旧CI或定向绿称发布通过 | 版本、收集面和环境都是证据身份；生产httpx与CI不同 |
| #30保留意图并列未替代接缝 | 看到新PR名字近似就宣布替代 | 真实函数和消费者行为不同，文本可合不证明语义已接替 |

## 证据与接手入口

新私有根：`~/.finance-runtime/reviews/release-resume-20261007/`。

- 远端：`main-before.json`、`open-prs-before.json`、`open-prs-current.json`（滚动观察）、`protection-readback.json`。
- 推送：`push-old-pr-refs-before.tsv`、`push-old-pr.log`、`push-old-pr-refs-after.tsv`、`push-old-pr-summary.json`。
- 增量扫描：`old-pr-delta-scans.json` 与各PR redacted报告。
- #51全量：`gate-pr51/` 固定a8fe098a；`pr51-full-receipts/gate-hihTN9bw/`；runner PID记录在
  `pr51-full-runner.pid`，运行结束才有 `pr51-full-summary.json`。不要仅据进度点号判成功。
- #30：`pr30-seams-{main,candidate}-v2.json`，脚本和范围见对照表。

测试解释器为主检出 `.venv-workbench/bin/python`，去除继承的个人/launcher变量。
全量临时目录 `pr51-full-basetemp` 显式保留，未删除旧目录或他人临时区；磁盘约19GiB余量，继续监控。
最终发布还需最终main的完整Python、前端和端到端收据、切换授权与生产健康/真实答卷检查。
本轮未合并、部署、改可见性或启动新模型批次，旧12题取消约束不变。

工具盘点：复用既有gate、收据checker、Git事务和CLI；本轮一次性批次包装与双revision取证
留在私有证据根，因固定此批head/历史反例，不制造第二套通用发布平台。通用凭据闸已在前轮
正式scripts与测试中，当前不扩展新规则。最新运行/推送状态由本分支inflight和API继续回读。
