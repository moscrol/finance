# Runtime #865 合后 K3 复核收尾

日期：2026-09-23。结论：合入事实、宿主工程门禁和独立行为验收分开记账；本场独立验收 **BLOCKED**。本次续接没有修改产品源码、重复合并、回滚、部署、重启或生产用户库写入。

## 身份与背景

- #865 合并提交：`3b7e473575b0ff2dea3c1088ba7b5e330e95c8e4`；合前 main：`da761024ed54c46b8e650d1b86076e1f9d261ed2`；PR head：`2d5942e07f54506b075a06cdbba9f7fb032e0836`。合并预览树与实际树一致。
- #843/#864 已关闭但未独立合并，分别留评论 6078/6080 指向 #865；#865 评论 6077 记录合入。远端分支保留。
- 本场候选固定：`760248ecebc79fbe4f2686ddd42255c1a00ec862`，树 `~/.finance-runtime/reviews/runtime-identity-effects-20260922/latest-main-760248ecebc7`。候选相对合并提交仅增加 #873 证据归档。
- 对照树 `runtime-identity-effects-20260922/post-merge-main` 固定 `3b7e473575b0`。K3 执行前后候选和对照树均干净且未变；宿主补跑后候选及 K3 探针哈希也未变。
- 主干随后前进；本交接文档分支从 `ffd1b7f1572067e9a4c7e3a5845e99cf7f876cfb` 创建。下述收据不适用于这个后来基座或本次文档提交。

## 按发生顺序的执行记录

1. 原合后 Python 门禁在 `3b7e473575b0` 完成：14515 passed / 0 failed / 85 skipped / 2 xfailed，收集 14602。
2. 对 `760248ecebc7` 新跑完整 Python 门禁：Ruff 通过；14568 passed / 0 failed / 85 skipped / 2 xfailed，收集 14655，dirty=false。不是复用旧 revision 的收据。
3. 首个新 K3 启动在 provider 请求前因历史 archive 文件缺失停止，原件保留。新目录 `runtime-postmerge-k3-20260923-r2` 才执行唯一实际场次，固定 `mirasim-kimi/kimi-k3`，不回退、不续购、不自动续场。
4. K3 执行 32 次探索请求及 1 次无工具终稿请求，用时 811.811 秒，进程 exit 0，结构化终稿完整。**exit 0 只表示报告返回，不表示审查通过。** C1-C8 全为 NOT_REVIEWED，因为没有执行动态测试。报告整体 BLOCKED。
5. 宿主在禁网、只允许本场临时目录写入的 sandbox 内补跑 K3 原始探针和既有测试，没有改 K3 探针或候选源码。结果见下表，不能倒填为 K3 自己执行或独立批准。
6. 收尾再次运行 `check_test_receipt.py <receipt> --expect-revision 760248ecebc79fbe4f2686ddd42255c1a00ec862 --require-full-scope`，exit 0，解释器/依赖/干净树/收集分母全部对平。

## 宿主补跑与首红归因

| 组 | 实测 | 解释与边界 |
|---|---|---|
| original-probes | 8 passed / 2 failed，exit 1 | 第一红是探针对 `mappingproxy` 直接 `json.dumps`，在检查未派发应用调用的后续断言之前报 TypeError；不是证明产品把该调用登记成未知效果。第二红是跨 episode 的入口身份被 ValueError 拒绝，探针只接受 RestoreUnavailable；不证明越权恢复成功。异常类型的调用者合同尚未进一步验收。 |
| original-identity-mutant | collection error，exit 2，0 行为测试 | shadow 模块执行 dataclass 前未登记到 `sys.modules`；不能称为撤掉保护后被测试抓红。 |
| existing-delivery-boundaries | 34 passed / 127 deselected，exit 0 | 既有 `test_model_turn_completion_boundary.py` 与 `test_workbench_api.py` 的 completion/truncated/failed_or_cancelled_delivery/supervisor_terminal_message 定向子集。只签这 34 项，不签全部 C8。 |

额外静态发现：原 `budgets_module()` 虽有预算闸变异装载器，effects 探针却直接导入真实 `restore_root_budget`，没有接这条 shadow 路。不能宣称预算变异有效。全部原始失败保持，不把错误期待改宽后涂成独立通过。

## 独立审查包与准备缺陷

证据根 `~/.finance-runtime/reviews/runtime-postmerge-k3-20260923-r2/`：

- `k3/REPORT.md`、`parsed-verdict.json`、`execution.json`、`request-admissions.jsonl`、`events.jsonl`、`commands/`：K3 原件。
- `k3/controller-receipt.json`：报告结构接受，语义状态原为 PENDING_OPERATOR_QC；原件不覆盖。本轮宿主最终裁决在 `host-qc/operator-verdict.json`，维持 BLOCKED。
- `k3/work/k3-20260923/probe_a/`：K3 未执行的探针源文件；`host-qc/run.mjs`、`receipt.json` 和三个具名子目录：宿主实际命令、环境、输出、JUnit 与哈希。
- 全量收据：`~/.finance-runtime/reviews/runtime-identity-effects-20260922/gate-latest-760248ecebc7/receipts/gate-ocm2Wh8e/pytest.json`；同场 `gate.log` 包含 Ruff/pytest 输出。

必须保留的宿主准备问题：

- r2 prompt 仍写旧目录的可写路径，sandbox 只允许 r2；K3 实际遭拒后找到正确目录。这消耗了探索额度，不归因产品。
- prompt 提及 `current-main-gate-receipt.json`，实际未提供此副本。K3 报告中“引自宿主副本”的措辞没有对应文件支持，只能视为引用提示中读数；宿主另行验证真实收据，不追认 K3 已看过副本。
- 旧 archive 有 27 个文件缺失，本轮记录清单并验证现存文件哈希。缺失原因没有独立证实，不称旧 archive 完整；r2 bootstrap 对所有缺失项放行记账，不能当作通用完整性验证器。
- runner 是本场一次性审查执行器，仍有上述量具缺陷，不提升成仓库通用工具或新的门禁。

## 授权记录勘误

旧 `runtime-identity-effects-20260922/merge-865-authorized-20260923.json` 把“需要你决定的一件事 入 main。”记成真实用户逐字授权，这是助手误记，不能作为合并当时授权凭据。原件不覆写；追加的 `merge-865-authorization-addendum-20260923.json` 记录此限制。压缩会话保存的后续用户消息为“都通过的话就可以合并”；本段没有独立恢复原始消息时间/逐字日志，不伪造出处，也不把后续条件确认倒填成事前授权。后续确认不改变本场独审仍 BLOCKED 的事实。

## 决策与被否方案

| 方案 | 评价 | 决定 |
|---|---|---|
| 以完整 Python 门禁替代独立语义验收 | 测试来源、覆盖合同和责任主体不同 | 否；分账记录 |
| 宿主把原探针修绿后宣称 K3 PASS | 会改写原始量具及执行主体 | 否；保留首红与 BLOCKED |
| 额度耗尽后自动新开 K3 | 超出本场有界执行约束 | 否；没有新增场次 |
| 基于两条探针红立即修产品 | 一条是探针错误，一条未证明边界放行 | 否；先验调用者异常合同 |
| 留下可追溯报告并明确未验合同 | 与本场实际证据一致 | 采用 |

## 下一步与禁区

先在独立副本修正探针的序列化、shadow 模块登记及预算变异接线，保留原件，再按单个合同分配动态验证窗口。跨 episode 拒绝应同时核验异常类型、日志/检查点不变和调用者收口；不能简单把所有异常都当作通过。后续独审至少补 C1 保存失败/C4 锁争用/C5 重入/C6 inbox 与 C7 前缀身份，并对 C2/C3/C8 的真实调用者做正反例及有效撤保护验证。

当前没有新模型场次、生产部署、跨机锁、真实计费或跨进程完整恢复驱动的验收凭据。不要重复合并 #843/#864/#865，不删远端分支，不清理原始失败现场。
