# 历史证据来源绑定集成验收（2026-09-21）

固定代码：`f90fd3dc3ba10a9a00f7264f92d3ec959b2ba682`，基于 #832 前向合流候选
`a14005fc9a9d671d178da6fc91be9cb69ae67e77`。这是独立 WIP 候选，未塞回 #832、未合 main、未部署。
**本次作者工程叶通过；不是独立审查，也不是自然金融质量通过。**

## 代码范围

- 历史证据恢复只对新增可选 `history_provenance` 做窄兼容：旧普通证据可缺该字段；历史工具证据必须严格重建来源身份，不能用 None 降级。
- `HistoricalEvidenceProvenance` 严格检查 query/算子/用途/ref/行坐标/16位小写行指纹/研究资格；证据哈希把历史控制元数据纳入统一身份，普通证据哈希保持旧算法。
- 查询与授权 reader 在投影、分块前规范化语义字段；行身份跨页稳定，行内 `·块N` 只区分公开卡；每块只带实际展示且数值精确相等的 observations。
- verifier 由合同 `allowed_history_operations` 决定何时启用历史资格门；启用后缺来源、伪来源、错算子、错 hash、locator/query key 不一致均拒绝。身份/哈希不证明上游原件真实性，原件认证仍由 RunStore 负责。
- `comparison_analog` 新增比较维度、假设、相似点、差异和类比限制槽；假设槽仍是模型推理，不冒充历史事实，不等于 #793 板块排序合同或 #794 Workbench UI。

## 作者工程收据

- **全量 Python**：`12635 passed, 87 skipped, 2 xfailed, 17 warnings`，无失败/错误，
  1178.14 秒。执行 `11:28:53.674761Z`–`11:48:44.705726Z`；首尾固定 f90fd3dc、clean、identity_stable。
  收据 `/Users/a77/.finance-runtime/test-receipts/20260921T114832Z-f90fd3dc.json`，
  `receipt-check.log.txt` exit 0，解释器/依赖/基座漂移5≤5均通过。JUnit完整原件由外部哈希清单绑定。
  87 skip 与 2 xfail 仍保留，未缩分母；归档XML中的类型明确是 87 `pytest.skip`、2 `pytest.xfail`。
- **前端六步**：安装、lint、typecheck、单测 **110P**、build、E2E **34P/2S**，每步exit0；
  `frontend/frontend.json` 首尾固定 f90、clean，日志大小/hash有回执。
- **全仓检查**：Ruff、registry parseability、registry check、backfill-tables --check、
  generate-views --check、ledger crosswalk 六条均exit0；`checks.json`逐条含命令、exit和日志SHA。
- **定向**：历史相关扩展回归最终 `177 passed in 9.12s`（v4，旧树c827的探针收据）；
  集成后focused `763 passed in 32.88s`；这些只用于定位/回归，不替代全量。
- **内存撤保护**：8项正式行为变异全部使各自目标测试转红、无收集错误，见 `mutations/summary.json`；这是作者诊断，不是独立签字。

## 真实原件离线回放

`artifact-replay.json`：固定历史原件 SHA256
`98b3746f5cc71027c3a5756ada1057f433a84acb98b65f3106b8c5c95e42d933`，9页 offset 0..200、每页25，
225/225行，分页累计905次证据卡严格恢复（含各页重复的范围/元数据卡，不是905个独立样本）；初次投影/授权reader的同源行卡相等、重叠页hash相等、所有特征等于原件、原件未变，模型调用0。
这是把真实JSON复制进临时RunStore后的投影/恢复回放，证明临时store的授权reader路径，不认证原始用户归属，也不证明模型自然引用或金融结论质量。

## 仍阻塞 / 不得外推

- 没有本轮独立 Spec/Quality 审查；不得把作者全量、变异或离线回放写成独立通过。
- 没有新的自然金融模型会话；旧 `not_passed` 保持。225/25 显式引用绑定、板块同窗/候选范围、#793 比较合同与 #794 真实 Workbench 消费仍另验。
- WIP #841 是本候选的接替入口，以#832分支为diff基线展示增量，未执行合入#832。#829原PR保持WIP/open，评论5416留接替指针，原提交不改；#833不在本次联合验收范围。
- f90执行时首尾净树；本归档是之后的docs-only提交，收据不移签新tip。`junit-comparison.json`确认相对a140多39P，89项skip/xfail名称、类型、理由完全一致。

## 证据和哈希

`sha256-manifest.txt` 绑定仓内全部归档（不含清单自身），提交后用
`scripts/check_evidence_archive.py docs/verification/2026-09-21-history-evidence-integration --revision <归档提交>`
核对Git内的完整文件集合和blob字节，不只核本地磁盘。`EXTERNAL-SHA256SUMS`绑定f90/a140完整JUnit XML及真实历史源工件；本包不含K3事件，K3属于#832的另一归档。
完整执行根是`~/.finance-runtime/reviews/react-trace-integration-20260921/`。临时执行目录和源代码树未随仓提交。
