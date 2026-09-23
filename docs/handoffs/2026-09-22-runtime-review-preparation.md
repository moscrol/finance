# Runtime #843 独立审查准备与授权阻塞

## 本轮范围

用户要求继续推进。开工分支 `fix/runtime-closeout-0921` 干净，HEAD `53f265d7c1969d5aba1378f42bd5433dc999ab38`。本轮仅核查审查入口、固定队列外材料并回写；没有新模型调用、独立审查、业务代码修改、测试执行、合并或部署。

前轮作者工程证据仍只绑定代码 `9fbcc9196a6834718a81c0bb11a8d6f495508b1d`，详见 [重入修复快照](2026-09-22-runtime-writer-reentry.md)。本轮不把它移签给文档 tip 或主干组合。

## 发现顺序

1. fetch 后 `gitea/main=e82717d9a7c3dfa811a4538bd44985b61258355a`；PR #843 open/WIP、未合、head 与候选一致，reviews=0。
2. Claude 认证状态为 `api_key_helper`，不能当作已确认免费订阅通道。Codex 虽登录 ChatGPT，仓内 `scripts/agent_review/REVIEWER_PROMPT.md` 明确其子会话 PASS 不具有独立权威。未调用任何模型验证认证。
3. 共享队列最新请求为 ARL-0022。最初用两个错误缩写提交号执行祖先判断，均 exit 128，不是“不在祖先链”的证据。读取 JSON 取完整 `e024baa66a2d8dece8e2bfc736777621079da06e` 后，`merge-base --is-ancestor` exit 0；已当场纠正先前口头判断。
4. `submit.py` 会将最新依赖提交设为差异基线，写 ready 请求；`reviewer_worker.sh` 有轮询模式。是否后台当前运行未证明，但不能把共享入队当作无副作用准备，也不能省略依赖或修改旧请求来缩范围。
5. 本机 `~/.finance-runtime/agent-review-loop/claude-oneshot-reviewer.py` 只给模型 diff 与预检结果，使用 `--tools` 空值；其默认 USD 上限 12 不是用户授权。它无法自主检查未展示调用方和执行新反例，不满足本次要求的独立反例审查。检查的是此适配器，不代表所有 Claude 审查方式都无工具。
6. 将完整 PR 差异、相对主干差异、代码到文档 tip 差异、源码身份、机械测试映射和作者收据副本放到队列外。未分配 ARL ID，未创建 request/claim/verdict。有限静态阅读不构成完整预审通过，也没有新增已验证缺陷结论。

## 决策与被否方案

| 方案 | 评价 | 决定 |
| --- | --- | --- |
| 直接启动 Claude | 认证可能计费，用户尚未授权新付费审核 | 等总额授权 |
| Codex 子会话代签 | 违反现有独立 reviewer 身份合同 | 否 |
| 共享队列先写 ready 再说 | 可被轮询消费，且差异基线退到 ARL-0022 | 本轮不入队 |
| 直接运行旧无工具适配器 | 可做 diff 语义检查，不能自主设计并执行反例 | 不当完整独立验收 |
| 队列外固定审查包 | 不触发 worker，记录范围与证据身份，不伪造审查权限 | 采用 |
| 再跑一轮作者全量 | 本轮未改代码，仍不能补独立性缺口 | 未重复执行 |

## 固定材料与核验

目录：`~/.finance-runtime/reviews/runtime-pr843-review-prep-20260922/`。

- `README.md`：范围、主要合同、待证伪项、启动阻塞与权限边界。
- `manifest.json`：状态 `PREPARED_NOT_QUEUED`，SHA256 `14fd155096d590fd05b6efca973600d97b24ed9a7db8dbbaf2c71b59e6ea4d79`。
- `pr.diff`：`79b11d4268a39e0c0ba1cca6e99fef46e338661e..53f265d7c1969d5aba1378f42bd5433dc999ab38`，完整84路径，包含导入的前置改动。
- `main-tree.diff`、`code-to-tip.diff`、`changed-paths.txt`、`artifact-tests.json` 及6份 `author-evidence/` 副本。机械发现253个唯一测试路径，不证明覆盖完整；本轮执行数为0。
- 12成员逐个 SHA256/字节数复核、84源码内容与固定 Git blob 复核通过。哈希证明材料一致，不证明实现正确或具有独立权威。
- 固定范围 `git diff --check` exit 0；源树生成前后均干净且同一提交。
- 候选与主干 `merge-tree --write-tree` exit 0，树 `3ac0bd2a8e6b3ca222c8a981566b11da6cb3a647`，相对候选仅 `docs/learning/ledger-map.md` 不同。未创建或测试实际合并提交；不同于前轮基于代码 SHA 的模拟树。

本轮未启动测试服务或后台 reviewer，无需清理新服务；其他会话进程未动。生产8792未访问或变更，不将历史health核查冒充本轮观测。

## 下一步与边界

先取得一次独立外审及总费用上限授权，再使用固定检出、可读源码且可执行隔离探针的 reviewer；超额/超时停止，不自动追加付费。正式 request 的基线、历史未决项和 scratch 探针写入边界必须明确，不能因新目录而抹去旧审查问题。现有 reviewer prompt 只准写 verdict，不可静默放宽。

审查范围包括保存失败父子熔断、预算/授权/证据快照、重复恢复、任务/实例/驱动锁、inbox收口、身份与磁盘前缀，以及恢复计划不授执行许可。发现反例后修复、重新固定版本，随后验最新主干组合。合并和部署分别待确认。

用户绑定、未知外部效果与费用对账、检查点后私有现场和完整续跑执行器仍待；自然金融质量另验。不能由本包推出自动续跑、跨机锁、exactly-once 或金融回答质量通过。

## 工具沉淀

复用现有 `discover_artifact_tests` 与 Git 对象查询生成一次性准备材料，没有新增 runtime/门禁能力或另造审查协议。暂不扩成通用脚本：这轮只执行一次，正式审查方式和授权合同尚待确定。队列写入也是副作用、哈希与权威分账均为既有方法，本轮只更新项目交接指针。
