# Ownership v3 · K3 独立审查尝试与根 QC

## 结论

**已按用户“用k3跑啊”使用现有 K3 通道。根 QC（操作员证据复核）判定需要修复 `CHANGES_REQUIRED`；两轴独立审查完成度仍为 `BLOCKED`。不能合并或上线。**

不是“模型不可用”：Spec（合同符合性）和 Quality（故障/边界质量）都实际执行了工具与探针。但两者都用满各自 40 次请求，没有完成最终报告。Quality 的文件只是启动时 `in_progress` 占位，不能当终审；根 QC 不代写模型结论。

确认一个高优先级问题 **O-K3-001：同一 Python 进程内嵌套调用 `pytest.main()` 时，内层会先写入外层专属收据；外层门禁返回 0，却读到内层的范围与测试数量。** Quality 自设计探针暴露，操作员另建最小仓、复制精确候选源码和环境契约复现。子进程嵌套对照正常。仅证明“证据认错主人”，**没有证明失败的外层测试会被接受**，也不追认旧全量读数已经受污染。

本轮没有修业务/门禁源码、合 main、部署、生产回填、购额、切付费 fallback（备用付费通道）、额外模型会话或删除真实工作树。Arena 另线未接管。用户选通道的纠偏已走项目 correction 入口，不再要求等待 Codex 或重新选模型。

## 固定身份与运行

- 候选：`47530e20fe5c3195e50ce429b31898d57918e413`。
- 历史比较基线：`728f327160bbd2485cb635e7ef09d040d718d7b5`。
- 只读审查树：`~/fwp-wt-ownership-{spec,quality}-v3-0921`；作者树 `~/fwp-wt-ownership-gates-v3-0921`；三树首尾及封存前均为相同候选、净树。未在这三树追加文档提交。
- 解释器：`~/finance-workspace-private/.venv-workbench/bin/python`；不是宿主 Python。
- Provider/model：`mirasim-kimi/kimi-k3`，本地入口 `http://127.0.0.1:18788/v1`，bootstrap 验现有 Plus 订阅。凭证仅内存注入，无 Keychain/token 内容归档。bootstrap 离线测试 9 项通过。
- 每轴只允 1 个会话、1200 秒、40 次请求准入；准入在发请求前预占，无自动重试/扩额。配置中的 cost 是估算，不是账单，也不是金额上限或“零花费”证明。

| 轴 | 实际请求/完成回答/工具 | 耗时 | 退出 | 最终报告 |
|---|---:|---:|---:|---|
| Spec | 40 / 40 / 42 | 1187.020s | 75 | 未产出 REPORT 或 verdict |
| Quality | 40 / 40 / 42 | 933.388s | 75 | 仅启动占位，未更新结论 |

第 41 次 turn_start（轮次开始事件）不等于第 41 次模型请求；bootstrap 拒绝后未发出。`stop_reason=null` 只表示外层 watchdog（超时终止器）未杀进程，不代表审查成功。两会话独立上下文/独立树、未读取对方输出，共用任务材料和同一模型；不是完全盲审或跨供应商评审。

## 读证据的顺序

1. `operator-qc/final-qc.json`：根裁决、独立完成状态和未验边界分列。
2. `operator-qc/quality-qc.md`：确认问题的位置、控制组、装置错误与具体未测项。
3. `operator-qc/inprocess-reproduction.json`：操作员复现，两场景真实 gate 均 exit 0；子进程组外层 1P，同进程组外层 stdout 1P、收据却内层 2P。
4. `operator-qc/reproduce_inprocess_receipt.py`：一次性复现脚本。`inprocess-reproduction/` 留命令、退出码、收据、shell 全输出和文本夹具。唯一建目录、拒绝覆盖，复制后勿在原输出重跑。归档代码后缀加 `.txt`，不是可执行安装。
5. `quality-trace/030-result.txt` 与 `quality-k3/logs/b4_nested_inproc.log`：原模型探针，未改写。原 toy receipt 因后续场景复用目录被删除，不能声称其原 JSON 仍存；操作员复现保留独占原 JSON。
6. `operator-qc/spec-qc.md`：Spec 195P/1S 的真实补充测试及其不能代替终审的理由。
7. 两轴 `execution.json` / `events.jsonl` / `request-admissions.jsonl` / `stderr.log`，以及 `*-tool-trace.json`、`*-trace/`：重建工具参数、写文件各版本、原始结果。
8. `operator-qc/preseal-observation.json`：当前身份、PR 状态、分母和上游漂移核对。

### 已有证据，不扩大分母

- Spec 正式候选定向测试：90P/1S + 105P = **195P/1S**，两份绑定同候选/同树的收据 `...2312ed82d8a6.json`、`...03899aeeb7c4.json`。另一个 `...1a04228dcb87.json` 是零执行收据，保留但排除；`latest.json` 只是导航。初版封存前收集脚本误以为仅两文件而断言失败，诊断原件 `operator-qc/preseal-collector-initial-failure.txt` 保留，未改原收据。
- Quality helper **39 个参数用例**记录真实子进程退出码，根 QC 逐一核对通过；不是 39 个独立端到端场景。真实并发两 gate 有不同唯一收据，测试目标/计数各自正确；真实子进程嵌套正常，同进程嵌套失败。IO/Git/signal/dirty/修正后的提交漂移探针有拒收证据。
- Board（工作树看板）只有部分模拟证据；Quality 命名使普通树归 `other`，不能签 clean-dev 候选分组，且没压基准扫描中变化。Quality 回填仅读源码、未完成独立动态用例；Spec 回填探针的夹具依赖/污染限制见根 QC。
- 历史 v3 作者工程门禁保留在 `2026-09-21-ownership-resume/`：Python 12068P/85S/2X、前端 110P、E2E 34P/2S、finance-only registry 五项成功；**本轮未重跑，不升级为独立通过，不移签新候选**。

## 装置、输出与权限边界

- K3 **没有操作系统沙箱**。源树只读、禁止额外网络和输出目录约束是任务合同，不是系统强制。缺 edit 工具不阻止 shell 写文件；首尾净树也不能证明期间未改后还原。
- Spec 确认一次越输出边界：写 `/tmp/a7.log`，原件未删，复制留在 `operator-qc/spec-outside-output-a7.log`。机械审计只查直接 write 路径，它的空违规列表不能覆盖 shell。
- 两轴各 16 个 bash 调用未填显式 timeout，多为读源码/诊断，违反每命令 <=120 秒约束；全局上限仍生效。具体索引见封存前观察。未发现 Quality 写其目录之外或两轴模型工具调用生产/凭证/应用端点；这是轨迹复核而非沙箱证明。
- Quality 的收尾提醒没变成硬阶段切换：第 28 请求之后继续扩探针，虽早建占位仍未写终审。不能用占位补齐缺失验收，也不自动续跑求绿。
- 夹具错误保留：Spec 未提交故意失败测试、探针 Ruff/import/mock/cwd 错误、Ruff 把 shell 当 Python 的 197 个假红、回填共享报告污染；Quality 未启收据 B1、错误 git 参数 B9、未清 toy worktree 注册。均按根 QC 归因，不冒称产品缺陷。
- 这里有完整 **shell 输出**，但原 `run_main_gate.sh` 内部仅保留 pytest 最后 15 行；Spec 两次正式测试外层也用了 tail。不能称完整 pytest stdout。合成仓/数据库/缓存保留本机，部分早期夹具与收据被模型重建，日志在，不保证每版二进制都在。

## 上游漂移补记（不改冻结输入）

授权/共用 prompt 中 `8aff6ebc...` 是早先观察，`Current upstream main at launch` 这句话在实际启动时已过期。实际执行身份为准：Spec `602ec8b7... → 2bb7c224...`；Quality `2bb7c224... → 945c04bd...`。封存前 `2026-09-21T04:52:08Z` 远端/local tracking main 均为 `3c70af64...`，三个 PR 仍 open/unmerged。Gitea 的 mergeable 字段只是服务端声称，不代替 merge-tree 或集成验收。本会话没合上游；这轮从始至终只审旧基线上的固定 v3，**没有最新 main 集成对象/测试**。

## 归档约定与下一步

原目录：`~/.finance-runtime/reviews/ownership-k3-v3-20260921/`；协调树归档 `docs/verification/2026-09-21-ownership-k3-v3/`。

`seal_evidence.py` 只选文本证据，拒绝覆盖新包，原字节复制；`.py/.sh/.mjs/.log` 追加 `.txt`，超过 4 MiB 的 JSONL 仅沿 LF 字节边界切片，manifest 记录原 SHA256、偏移、顺序。按 ordered_parts 拼接应逐字节等于原流。不打包 token、数据库、Git 对象或缓存；脚本/探针只是有限证据装置，没有安装调度器。文件数从 manifest 解析（含 README，不含 manifest），不人工猜。

旧四代包分别为首轮失败、v2 历史作者绿、v3 历史作者绿、Codex 阻塞，全部保留原义。`verify_archives.py` 在封存后核五代包的成员/长度/哈希/原始来源和旧包 Git HEAD 字节一致；结果另存协调收尾目录，避免把验证结果写回已封包造成循环。

下一步需用户明确选择修复：把收据主人绑定到 pytest **调用实例**而非只看进程号，再加同进程/子进程/并发回归，新代码冻结后重验。**修复执行、追加独立审查预算、最新 main 合流、生产全副本演练、合并、部署、真实回填与删树均不从本轮自动继承授权。** 不再把修 Codex 作为 K3 审查的前置。
