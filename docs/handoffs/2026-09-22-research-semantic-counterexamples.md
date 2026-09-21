# 研究语义反例离线固化（2026-09-22）

## 背景与范围

用户要求继续推进。前轮清单身份、逐项 `requirement_checks`、公开 E 编号、最终 witness 复核及有限修复已经有工程收据，但不证明模型会正确理解研究结论。Knevo 三方审读暴露的 K2/K3/K4/K5 是本轮首要输入，另带 K7 的无校准确认标准。

工作树 `fix/research-contract-citations-0921`。研究截止日仍是 2026-09-21，不随本轮日期变更。只新增离线案例与测试，没有调用真实模型、访问 8792、重跑三题、改写数据库或原始运行。共享记忆项目页仍有他人未提交改动，本轮未接管。

## 按发现顺序

1. 查现有 `finance_answer_rubric`、`semantic_acceptance`、`judge_validity`、`episode_semantic_verifier`。现役服务有事实越界/因果越界理由码和清单回执，无需新建线上判官。代码地图 query 返回 empty/unavailable；本轮依据精确源码读取，不从空图推断架构。
2. 新建 `intelligence/eval/cases/research_semantic_counterexamples.json`：8 个改编案例，各有错误/可接受两个变体。公司与数字均为合成，`source_anchor` 指向审读失败形状；作者预期明确标 `author_proposed_not_independently_adjudicated`，不是原答重放或金融金标。
3. 首轮测试发现句后 `[E1]` 被生产分句器独立编号。早期临时映射另设了内容句号，不适合作为最终合同；最终只把合成案例引用移到句内，直接使用生产句号，没有改原件或生产编号器。
4. 初版 `7209bbfff` 只测拒句解析，覆盖不足。后续 `a8bc27e36050ae0262ef82a5c7a896fc873eddc1` 改为复用现有 `_case`、结构验证、`_judge_request`，检查原题要求、证据正文、E 号、无内部 hash/预期标签泄漏；再测 JSON、工具、注入式报告及最终公开稿覆盖状态。工具测试构造器漏 `content` 曾导致 16 个 TypeError，修正后复跑；这些不是语义失败。
5. K3 两变体还走完整 `verify`，但 judge 是固定返回值的测试替身。另设限制刻画：把 K3 错误摘要谎报 fulfilled，位置复核会保留 completed；真正删除 witness 才会降 partial。这不是通过语义验收，而是明确机械层不能理解必要条件。

## 预期裁决与被否方案

| 选择 | 被否方案 | 理由 |
| --- | --- | --- |
| K2 未核转确认：拒第2句；诚实披露版仍 partial | 谨慎表达直接算完成 | 用户要求核实实际报价，资料缺口仍未解决 |
| K3 摘要条件漂移：事实拒句为空，第2项 partial | 为降级而虚构事实错句 | 本合成题明确是自设研究条件，缺的是正文与摘要一致；不推广为所有摘要错误都不能拒句 |
| K4 拆成检索缺口外推和不披露当反证 | 用一个“未知”标签包办 | 前者是证据范围错误，后者是竞争解释的因果推断错误 |
| K5 拆成全链核实、正增长与行业外推、单日量价越级归因 | 有正确数字就放过整句 | 数字存在不证明文字解释、机制或范围正确 |
| K7 无具体数字的虚假历史标定 | 只测数字阈值机械门 | 本例专测“已经验证”身份伪造，不把数字出现当语义证据 |
| 成对样本、作者预期与请求分离 | 把固定裁决通过冒充模型能力 | 同时保留漏判与误杀方向，标签不送入待评请求 |
| 只改案例和测试 | 字符串硬门禁、扩写生产 prompt | 否定范围与必要条件需要语义上下文，单批样本不足以直接固化研究规则 |

## 已验证与收据

固定、干净代码提交 `a8bc27e36`：

- 五文件回归 **342 passed / 0 failed / 0 skipped**。收据 `~/.finance-runtime/test-receipts/20260921T184202Z-a8bc27e3.json`，`dirty=false`，`worktree_dirty_total=0`。
- 恢复后同组 **342 passed**：`20260921T184304Z-a8bc27e3.json`。
- 两个进程内反向检查：撤覆盖降级后 K3 出现 `completed != partial`；撤回执协调后状态列表为空。JUnit 均为预期 AssertionError、无收集/夹具 error，不以非零 exit 自动算成功。
- JUnit 在 `~/.finance-runtime/reviews/research-contract-citations-0921/`：`semantic-examples-fixed-a8bc27e36.xml`、`semantic-examples-restored-a8bc27e36.xml`、`semantic-examples-a8bc27e36-no-coverage.xml`、`semantic-examples-a8bc27e36-no-receipt.xml`。
- 上述命令复用 `scripts/review_probes/check_research_contract_boundaries.py --child`，只对测试进程 socket.connect 加 audit hook；不是任意子进程外呼沙箱。新测试额外拦常见 socket/Popen/真实 complete，关闭来源复查，并注入空 provider chain。
- 新测试 Ruff check/format、`git diff --check`、两个代码提交的 pre-commit 通过。新文件专属测试为 84 项，五文件总数以收据为准。
- 冻结 manifest 的 67 文件、Knevo intake 收据的 4 原件，大小及 SHA256 全部一致。
- 相对业务提交 `ba18395ce`，`intelligence/services` 与 `intelligence/runtime` 无 diff。

早期 67/200 passed 属于 `31cb2ff3c` 加未提交改动的开发态，不可代签干净 SHA；初版 `7209bbfff` 也不代表最终测试覆盖。

可复跑命令（项目规定用主树 workbench venv，以下 `$PY` 指该解释器）：

```bash
$PY scripts/review_probes/check_research_contract_boundaries.py --child baseline -q \
  intelligence/tests/test_research_semantic_counterexamples.py \
  intelligence/tests/test_research_requirement_review.py \
  intelligence/tests/test_episode_semantic_verifier.py \
  intelligence/tests/test_research_request_boundaries.py \
  intelligence/tests/test_public_citation_identity.py
```

## 不成立的结论与下一步

- 本轮未测真实模型识别率。16 个变体不是16次真实研究，342次测试不是342个语义样本。没有调用模型消费 Knevo 名额或重写冻结首答。
- K3 有完整 verifier 的固定报告测试；其余案例只压请求/回执/覆盖消费者，未证明所有拒句修复路径或预算重入的自然表现。
- 合成证据统一借用测试夹具 `market_data` 通道，只验证证据投影合同，不代表真实财经取证装配。来源复查关闭，没有外核金融事实。
- 未跑独立代码审核、全仓 Python、前端/E2E、跨仓 registry 或最新主干组合验证，未推送/合并/部署。生产行为仍是前轮业务代码，不宣称本轮让答案更准确。
- 先独立审核案例标签；真实模型须另获授权并用新样本。新案例请求和人工标签应隔离，按事实漏判、误杀、任务覆盖、修复后最终状态分别记录，不合成一个“全绿”数字。
- 工具盘点：复用现有进程内变异脚本，无新 CLI 或通用工具；本批需要语义裁决且未独立审核，不升级共享方法论/能力图谱，不改 `harness-reference` 在途内容。
