# T3 可信正文误删返修与冻结门禁 · 2026-09-19

## 结论

在原 `q/research-data-readiness` 接续，业务修复 **`a2a3301963d11a073f511e1552b53daee7ecd704`** 已提交并推 Gitea。原六例反例未改题/断言/标点，现 6P/0F；固定提交全量工程检查及 17 组撤保护检查通过。

**仍不合 main，不部署。** 独立审查 CLI 尝试一次，600 秒超时，无有效裁决；隔离预检通过不是独立审查通过。自然模型回答本轮 0 会话，旧 `not_passed` 不翻案。Gitea main 在本次核验时仍为 `b22ddf8b0285a952de1e6e18c04db0f4abe448e7`。

## 背景与发现顺序

1. 前次 QC `d38dab3f` 仅留证：d12 工程全绿，但“可信收入事实[E1]，但查询返回空白，因此公司没有公告”在真实 verifier 出口被整句删掉，引用卡也丢失。原始红保留在 `docs/verification/2026-09-19-t3-convergence/`。
2. 用户“继续”后，先加回归，再改实现。首次新增/扩展套件 49F/61P；初修四文件 157P，扩大定向 546P；补“但/但是”前缀边界后局部 152P。以上全是未提交迭代，不能当冻结收据。
3. 实现检测上下文与删除范围分离；顺查同源比率正文整句删除，改为仅把错值/单位标“待核对”。没有扩大模型预算、另起取数或补写链，没有静默填写正确数字。
4. 冻结 a2 后跑全量 Python、前端、E2E、固定三仓 registry、旧原样六例和 research-delivery 变异套件；前后代码树均干净。
5. 独立审查沿已有 `scripts.agent_review.submit/worker` 协议，隔离 state root、精确提交、不可变 request/claim、全量改动路径清单。隔离 worker 的 159P、旧六例和 17 组变异已跑完；随后 Claude `--model sonnet` 无工具审查未在 600 秒内返回，未产出 verdict。原样保全，没有重试、换模型、写自评为外评或放宽合入条件。

## 实现及取舍

| 方案 | 评价 | 结果 |
|---|---|---|
| 全局按逗号分句再检测 | 会拆散“查询为空→错误结论”的关系，漏拒错 | 否 |
| 保留整句检测，但删除整句 | 同句独立事实和引用被连坐 | 否，原反例仍存 |
| 整句仅作检测上下文，原文坐标定位错误分句 | 兼顾拒错与保真；合并相邻错误区间，保留存活分句的分隔及句末符号 | 采用 |
| 比率正文整句删掉或自动替成正确数 | 分别损害邻值/引用或代模型作答 | 否 |
| 按去格式文本识别、映射回原文错值/单位 | 保留报告期、Markdown、同期正确值与引用；同句多错值均标待核对 | 采用 |
| 另开热点实现线或整个吸收 T4/T2 | 扩大冲突，未先裁决行为重叠 | 否 |
| 用工程绿或预检绿代签独立审查 | CLI 成功启动/worker exit 0 均不证明审查成功 | 否，当前阻合 |

核心：`intelligence/services/research_delivery_checks.py`；新回归：`intelligence/tests/test_research_delivery_retention.py`；原续修/最终投影回归在 `test_research_delivery_repair.py` 扩矩阵。入口说明与错误教训随业务提交一起更新。

这仍是有限显式句式检查，不是通用自然语言解析器、公式正确性或证据蕴含证明；跨分句修饰、任意复杂 Markdown 等更广语义未被认证。

## 冻结验证（只签 a2a33019 完整 SHA）

| 检查 | 本轮结果 | 收据 |
|---|---|---|
| Ruff 全仓 | exit 0 | `candidate-a2a33019/ruff.log.txt` |
| Python 全量 | **11754P / 0F / 0E / 87S / 2xfailed** | `candidate-a2a33019/pytest-full.log.txt`、`full-python-receipt.json` |
| 收据资格 | revision、完整目标、解释器、依赖、干净树、base drift 0 通过 | `candidate-a2a33019/receipt-validation.log.txt` |
| 前端 | lint/typecheck/build 各 exit 0；**110P** | `candidate-a2a33019/frontend-*.log.txt` |
| E2E | **34P / 2S** | `candidate-a2a33019/e2e.log.txt` |
| 固定三仓 registry | parseability/check/tables/views/crosswalk 五项 exit 0 | `candidate-a2a33019/registry-*.log.txt` |
| 原样反例 | **6P/0F**，原文件与 d38 无差 | `candidate-a2a33019/original-fact-retention-probe.log.txt` |
| 撤保护验证 | 17 组全部被测出，逐项还原绿；套件首尾 **182P** | `candidate-a2a33019/mutations/results.json`、每组 diff/log/JUnit |
| 独立审查预检 | 四文件 **159P**、旧六例 6P、17 变异通过 | `qc/runs/ARL-0001/preflight.json` |
| 独立模型裁决 | **无结论**；一次 CLI 尝试 600 秒超时 | `qc-worker.log.txt`、`qc/runs/ARL-0001/reviewer.log.txt` |

原件根 `~/.finance-runtime/convergence-20260919/retention-repair/`；仓内原字节档案 `docs/verification/2026-09-19-t3-retention-repair/` 的 manifest 记录路径/字节/SHA-256。原全量收据：`~/.finance-runtime/test-receipts/20260919T050206Z-a2a33019.json`，不能用并发 `latest.json` 替代。

固定跨仓版本：Finance=a2a3301963d11a073f511e1552b53daee7ecd704；KB=1254224be89e2c4974350b7f3e985dbedb5dc043；site=f606583867fe1cad8de96b06be1dd6cfe2b57e51。三仓前后干净，未改 registry 登记，旧宿主错配首红不覆盖。

本轮所有 Python 检查使用主树 `.venv-workbench/bin/python`、清洁环境、umask022。E2E 使用 8914/8915 与隔离用户/台账，最终无残留监听。修复增加的测试与旧全量不能只按通过数相减；本轮记录真实 skip 数，没有新增 xfail/skip 把反例隐藏。

## 独立审查失败边界

- request `ARL-0001` 位于本轮独占 `retention-repair/qc`（不是全局 review 队列的 ARL-0001），hash `f788d85a8717eb73aa5d33476317ea4e9ae85def9fc1084213908fb9c69646be`，绑定 a2。
- 外层 worker 报 `REVIEWER_INACTIVE/failure_kind=transport`，日志进一步定位为子进程 `TimeoutExpired`（600 秒）。**不据此猜凭据、额度或上游挂了**。
- 一次审查 CLI 尝试；真实 provider 请求数、响应模型身份、token/费用均未知。不能说“本轮所有模型调用为0”；只有金融自然会话为0、工程测试自身无模型。
- worker 进程 exit 0 不是验收通过；没有 `verdicts/ARL-0001.json`，更没有 PASS。worker 的临时审查树已回收，未动现有其他 Claude 进程。
- 不自动重试或修改全局审查设施。本轮一次性编排脚本只作 `.py.txt` 证据，不安装成第二永久 runner。

## 下一步与不要做的

1. 补齐对精确 a2 的独立代码裁决；若改业务，重新冻结 SHA、旧原样反例、变异与完整门禁全部重验。独立预检/自审不能代签。
2. 固定代码/题目/证据/模型与兜底/预算，走真实 conversations 的自然回答验收。GLM flash/5.3 已有用户授权，不等旧 GPT Keychain；不挑绿、不同时改代码和证据。
3. 所有准入条件齐全后才继续既有条件授权的合入；部署另办。当前不继续 T5、T4/T2、T1 的合并。
4. 8792、夜跑 wrapper、KB 防写、他人主检出树均未动；shim salvage 仍只是档案。不要以“已备份”授权清理。
5. 文档归档提交不会被 a2 的收据自动认证为该新 SHA 全量绿；若要合最终 tip，需对最终 tip 另出精确收据，不递归提交每次收据改变被验目标。

## 工具与方法沉淀

原六例探针保持不动；新增范围回归进入标准 pytest，四个新增撤保护条目接既有 research-delivery suite（总17组），不是只有手法提醒。可迁移原则写回既有 `contract-vs-delivery-mismatch`：**检测窗口可以宽，修改权限必须窄；文本去格式后要映射原文坐标**。适用于脱敏、内容审核和自动修复。共享 harness-reference 的 BUILD.md 存在他人改动且 HEAD 领先 gitea/main，未覆盖；方法与工具指针先回已有知识笔记，不另建能力清单。
