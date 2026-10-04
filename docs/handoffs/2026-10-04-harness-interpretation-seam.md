# Harness 解释接纳接缝：最新主线集成与发布前阻塞

## 背景与范围

用户要求继续优化，并在验收通过后部署；同时问 Knevo 是否靠更强模型取得更好回答。
这不是把「程序测试通过」改名为「回答质量通过」的授权。Knevo 现有证据只有保存对话、
工具卡及自述，没有源码或实际模型身份；不能据此断言它没有 harness，也不能把效果归因于某型号。
本轮先处理独立 Standards 已复现的 S1，不扩剩余 P1b、共享记忆或模型实验。

任务板：FINANCEWORKS-1 / FINANCEWORKS-3。本会话已读取父子任务及评论，用 version 5
认领子任务至 in_progress；其他验收者仍只读候选，不触碰其他活动树。

## 按发现顺序

1. 核对起点 `3f82f9d1c1112cb080a82b0d4a7647e977a2fce3`、实际主线
   `108835e27d2e926ffd95077536badb6d061ea096` 和生产软链 `finance-workspace-ffe1c60d84da`。
   旧工程验收只覆盖 `06198093e` 基线，不能借旧绿跳过主线更新。
2. 重新读取外部独审：Spec 已检查 `5070054a0`，认为原反馈补丁在四片承诺范围没有确定回归；
   Standards 在 `60ff5ba76` 保留 S1：首轮自定义规则生效，合法解释 PLAN 接纳后又注回默认规则。
   两份报告分别在 `~/.finance-runtime/harness-quality-closeout-1003/pr30-{spec-5070054,standards-60ff5ba}.md`。
   它们不是本轮新模型调用，也不覆盖新补丁。此前独立 G10 异常违规结论已撤回，不据此扩修。
3. 无冲突并入固定主线，合并提交 `28cf79c44e58b0c16a27231132ee4ef98f0d0240`。
   主线留出集说明有三行 Markdown 两空格硬换行，使默认 `git diff --check` exit 2；保留上游原文，
   不把它冒充冲突或新产品错误。合并索引逐项等于主线差异，无未归属改动；提交钩子通过。
4. 新增三条 loop × 接纳/拒绝六组反例，原实现六组红：注入 harness 的接纳方法未被调用。
   `ResearchHarness` 增加 `admit_interpretation`，返回 `InterpretationAdmission`，统一领域接纳与反馈。
   连续 Episode、参考 loop、SDK hook 应用该结果，不直接调领域接纳函数。
5. 迭代时还修正三处测试夹具错误：工具 context 并非 ResearchRunContext、JSON list/tuple 比较、
   新参数化用例复用 live Episode ID。错误日志均保留，不计作生产 bug 或修复收益。
   最终相关273项离线测试通过；真实 SDK 生命周期用脚本模型验证，不是 provider 质量测试。
6. 产品补丁提交 `25de6994bdb79b57e9cf06fcb81f6f5796c67079`，已推 GitHub PR #30，Draft / OPEN / 无 auto-merge。
   Gitea 同名 feature ref 回读精确为此 SHA。随后固定该 SHA 跑完整本机门禁及变异；原历史证据不动。

## 决策与替代方案

| 方案 | 评价 | 裁决 |
|---|---|---|
| 在既有 ResearchHarness 增加带 context 的接纳结果和模型反馈 | 同一处拥有根/版本判断与给模型的话；默认实现纯委托旧领域函数，不换语义 | 采用 |
| 只改开场 prompt 或复制一份默认反馈到各 loop | 无法让替换 harness 控制完整协议，原 S1 仍在 | 否 |
| 把取消、截止、次数、事件、预算、持久化搬进 harness | 破坏既有领域/底座分工，不是 S1 所需 | 否 |
| 让替换 harness 缺新方法时静默回落 Finance 默认 | 会重现被测的绕过注入，兼容表象掩盖协议缺口 | 否；新方法属于 Protocol |
| 扩到恢复 finalizer / SDK repair 提示改造 | 最新 Standards 已明确不作为本项硬违规；会扩大行为与审查面 | 本轮不做 |
| 给每种坏提案再造一套异常恢复框架 | 旧严格领域构造校验保留；跨接缝只把预期 ValueError 转成结构化拒绝 | 否 |
| 直接靠全量测试和12格小样本上线 | 前者不证明内容质量，后者不足以检验父任务效应阈值 | 否 |

连续 Episode 仍先检查点持久化后继续；工具同包、取消、deadline、修复轮及 PLAN 次数上限
仍由 loop 守住。接纳只版本化目标，不重建 TaskFrame/合同/证据/根预算。
SDK 原有普通 PLAN 反馈形状保留，loop 只额外写 accepted_plan_revision。
生成目录 `docs/runtime/harness-seams.md` 经 `scripts/gen_runtime_catalog.py` 更新，没有手改。

## 固定25de的证据

证据根：`~/.finance-runtime/reviews/harness-release-20261004/`。

- `s1/red.log` 六项先红；`green-initial.log`、`green.log`、`green-r2.log` 保留夹具失败；
  `green-r3.log` 273 passed。仅迭代读数，不能代全量。
- `gates-25de6994/python-receipts/gate-GagU8L4S/pytest.json`：20584 passed、76 skipped、2 xfailed，
  0 failed/error/xpassed，collected 20662；18 warnings。解释器3.12.13，依赖指纹66726d345bf37ce5，
  dirty=false、未绕过依赖门禁。`python-gate.exit` 与 `python-receipt-audit.exit` 均0，完整范围审计在HEAD=25de时完成。
- `gates-25de6994/frontend/frontend.json`：六步exit0，complete/identity_stable=true、dirty=false；
  22 files / 209 unit、Playwright 52 passed / 2 skipped。测试服务部署账本是独立测试产物，不代表生产部署。
- registry五项exit0，反向回指warning原文保留在 `registry-ledger.log`，不宣称零warning。
- `mutations-25de6994/audit-final.json`：四组9/15/13/14，共51个定义捕获；
  baseline/restored分别321/321、56/56、54/54、287/287；历史8、边界16。
  三个新增变异分别绕过三条loop的注入harness，行为测试变红，恢复后变绿。
- 收集脚本仅树外批次包装，复用仓内门禁/变异入口；没有第二套产品或实验运行器。
  变异审计复用旧审计逻辑，在新路径固定新SHA，未修改旧原件。
- GitHub产品头：workbench run `37150212381`，registry run `37150212352`。
  本快照记录时registry/frontend/e2e已成功，Python仍在跑，不能宣称整体CI通过；最终状态回读PR和树外原件。
  一次 `gh run watch` 在工具300秒上限中断，保留日志；没有从缺少退出码推出成功。
- 本轮无真实金融模型调用，也没有启动新的编码模型独审。273项和全量/变异都不是独立代码审查。

## 清理与保全

前端独占门禁树 `gate-trees/frontend-25de6994` 完成后点名 dry-run→apply。
`frontend-closeout/apply-20261004T041339.json`：removed1、failed/skipped0；260残留文件与3数据库本地保全，
代码archive ref推Gitea并回读；`integrity.json`逐项核对tar、文件数、数据库哈希与工作树消失。
没有把本地数据归档描述成已上传Gitea。四个临时变异树由既有运行器在还原验绿后移除，已核对不在磁盘。
本轮活动集成树、原 `harness-integration-20261003/gate-trees/mutation-fix` 和其它会话树不动。

## 阻塞与下一步

- 新25de补丁尚无独立Spec/Standards结论；任务板已请求只读复核，不把请求当完成。
- 真实Workbench配对的型号/通道、价格、物理调用与token/时间/货币硬帽尚未冻结。
  树外 `model-acceptance-approval-draft.md` 提议新增审查+首批预验共50元、最多12格，等待用户批准；
  50元是建议上限，不是报价。现有静态价目表不证明实际代理计价，`glm-5.3*`不等于flash已核价。
- 12格只作预验，不能代签父任务双模型效果或直接发布；正式质量门需另有冻结方案。
  R17/R19/正式240格原账不动，新留出集不能拿来调参后再称留出。
- 用户条件授权已记录，但质量门未过：不合入main、不切8792、不改生产launcher/模型配置。
- 后续文档HEAD、本地25de产品收据、PR实际head分列；若再改代码或main推进，重新固定验收范围。
  不为抄写CI状态反复提交文档，不转签历史绿。

## 工具沉淀盘点

补洞落在可执行的Protocol、跨三loop行为测试与三条变异定义；新领域接缝复用既有设计。
树外脚本只绑定本轮固定SHA与证据目录，不是新的通用框架，故不迁到产品scripts，也不修改脏且底旧的harness-reference。
可迁移经验是「替换接口必须同时控制准入与后续反馈，用替换实现的反例验证」，本轮先固化在这些测试里。
