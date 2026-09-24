# 2026-09-19 · shim 封存与 T3 合流验收：发现保留缺陷，停止合入

## 裁决与范围

用户要求“执行”后，先封存指定三个 shim，再接续已有 `q/research-data-readiness` 候选验收；任何红项或无结论不合 main。本轮没有另开热点实现线，没有修业务代码，没有新自然模型会话，没有合 main 或部署。**T3 合入裁决：blocked**，不是“全量工程通过所以可合”。

固定被审业务代码 `d12bd0b1f5be2f242a1275fd51162f0e46cf5e3b`，基线 `gitea/main=b22ddf8b0285a952de1e6e18c04db0f4abe448e7`。候选已包含该基线；本地 `merge-tree` 无文本冲突，但行为验收发现下述阻塞。后续本枝提交仅增加 QC 探针、证据和交接，旧全量收据不替这些新提交或未来合流提交作保。

## 按发现顺序

### 1. shim 保全已完成，不安装旧代码

`salvage/opc-shims-20260919@1cc7fb140a92efd3bad637c3dc62f351bb6b9ab8` 已推 Gitea。三个来源文件：

- `intelligence/workflows/daily_review.py`
- `scripts/check_daily_review_data.py`
- `scripts/check_daily_plan_local.py`

原字节以 `.py.txt` 保存在该分支 `docs/verification/2026-09-19-opc-shims/`；manifest 绑定原路径、字节数、SHA-256、Git blob。已比较原主树文件与提交内档案逐字节一致。原主树的他人改动未清理、未覆盖。

09-18 夜跑实际使用冻结生成根 `finance-generation-387028b846a2`，不依赖上述三个 shim。这撤销了“昨晚靠 shim”的判断，**不等于授权清理旧树**。该 salvage 分支仅供恢复，不合 main、不部署。#50 源码合流另办。

### 2. 核已有全量，补齐其余工程叶子

复用已有**同一干净 revision**的 Python 全量，不冒称本轮重跑：

- 收据 `~/.finance-runtime/test-receipts/20260919T025205Z-d12bd0b1.json`。
- 11681 passed / 0 failed / 0 error / 85 skipped；原日志另有 2 xfailed；Ruff exit 0。
- `check_test_receipt.py --expect-revision <完整 d12 SHA> --require-target /Users/a77/fwp-q-research-data-readiness --base-drift-max 0` exit 0，核对解释器、依赖指纹、干净树和基座。

本轮新增检查：

| 项 | 结果 | 边界 |
|---|---|---|
| 定向 Python | 174 passed | 七个研究交付/资金边界测试文件；不是全量 |
| frontend lint / typecheck / build | 各 exit 0 | 构建后候选仍干净 |
| frontend test | 110 passed | Vitest |
| E2E | 34 passed / 2 skipped | 8914/8915 隔离端口，未触生产 |
| registry 原宿主布局 | check exit 1，其余四项 exit 0 | 首红保留，不删除 |
| registry 固定三仓布局 | 五项 exit 0 | 见下一节 |

使用主树 `.venv-workbench/bin/python`、清洁环境及 umask 022。新定向收据 `20260919T032357Z-d12bd0b1.json` **不是全量收据**，勿因它较新就替代旧全量。

### 3. 定位跨仓环境红，不回退登记刷绿

`build_registry.py` 默认扫描 Finance worktree 的同级仓。原主 KB 检出停在 `8a413cde` 且有他人改动；其 `rag-query` 哈希为 `193e7888…`，Finance 注册表期望已合主干的新版 `28246007…`。本轮没有重扫覆盖注册表、没有重置 KB。

固定布局 `~/.finance-runtime/convergence-20260919/registry-pinned/`：

| 仓 | 固定 revision |
|---|---|
| finance-workspace-private | `d12bd0b1f5be2f242a1275fd51162f0e46cf5e3b` |
| knowledge-base-private | `1254224be89e2c4974350b7f3e985dbedb5dc043` |
| finance-research-site | `f606583867fe1cad8de96b06be1dd6cfe2b57e51` |

KB 引用先前验收保留的干净 worktree；其余为 detached 检出，无新实现分支。三仓前后都干净。原样执行 parseability、check、tables、views、ledger-crosswalk，全部 exit 0。此结果只解除原宿主版本错配，不替业务行为或自然回答质量背书。

### 4. 独立反例：逗号使可信事实和引用被连坐删除（P1，合入阻塞）

位置：`intelligence/services/research_delivery_checks.py:37,53–66`，实际出口 `episode_semantic_verifier.py::_recheck_research_delivery`。

输入只变分隔标点，证据、错误推断、trace 完全相同：

> 中报原文披露了收入[E1]，但查询返回空白，因此公司没有公告。

应拒绝的是后半段“查询空白 ⇒ 公司没有公告”，不能连带删除有独立来源的收入事实和 `[E1]`。

| 分隔符 | judge off | judge llm（确定性替身） |
|---|---|---|
| `。` | 正确事实及引用保留 | 正确事实及引用保留 |
| `；` | 正确事实及引用保留 | 正确事实及引用保留 |
| `，` | **事实和引用均消失** | **事实和引用均消失** |

逗号用例最终公开正文只剩：

> 公告检索范围尚未核实完整；不能据此断言公司没有公告或尚未兑现。

两种模式下状态诚实为 partial，私有原始证据仍在；**私有保留不等于公开交付保留**，`delivery_retained_evidence_hashes` 也为空。既有定向测试使用句号隔开可信事实，未覆盖这个反例。

根因：`_CLAUSE` 不按逗号分段。检测逻辑虽按逗号收窄否定语气，最终 `DeliveryFinding` 却仍返回整个 `_CLAUSE` 的起止位置，删除粒度比错误断言大。

新探针 `scripts/review_probes/check_delivery_fact_retention.py` 在干净固定代码上走真正的 `SemanticEpisodeVerifier.verify` 和最终 recheck：**4 pass / 2 fail，exit 1**。它同时验错误被拒、事实与显式引用/绑定保留、原始证据不变、缺口说明、partial 状态和重验幂等。未调模型/网络，`llm` 使用成功替身，不能冒充真实问答或修复续跑。

## 决策与被否方案

| 选择 | 否掉什么 | 原因 |
|---|---|---|
| 旧 shim 按原字节档案封存 | 直接放回 main 源码路径 | 会把备份误装为实现并回退新代码 |
| 接续已有 q 候选 | 新开同热点整合线 | 避免扩大平行冲突 |
| 钉住所有参与仓版本重验 registry | 按旧 KB 扫描并覆盖新登记 | 应纠正检验输入，不把正确登记改旧 |
| 保留首红和条件化复验 | 用后一次绿覆盖之前记录 | 两次检查条件不同 |
| 行为红即停止合入 | 因 11681P/174P/前端绿而合入 | 这些测试没有覆盖逗号造成的误删 |
| 保存反例交给原整合线修 | 本轮再叠新守卫或替换 T4/T2 方案 | 当前是验收；行为粒度需先裁决再改 |

## 收据与可重跑入口

原件根：`~/.finance-runtime/convergence-20260919/`。仓内归档：`docs/verification/2026-09-19-t3-convergence/`，manifest 为每件原始文件绑定字节数与 SHA-256。

- `t3-d12bd0b1/result.json`：工程补检及原宿主 registry 红。
- `t3-d12bd0b1/prior-python-receipt.json`、原全量/ruff 日志：已存在全量的复制件。
- `registry-pins.json`、`registry-fixed-results/result.json`：固定三仓和复验结果。
- `fact-retention-probe.json` / `.exit`：独立反例原始结果。
- `run_t3_remaining_checks.py.txt`：一次性编排器原件，仅存档；常规门禁继续使用既有入口，不另造永久硬编码 runner。

复跑反例（解释器用主树 venv；代码根保持干净）：

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  scripts/review_probes/check_delivery_fact_retention.py \
  --code-root /Users/a77/.finance-runtime/convergence-20260919/registry-pinned/finance-workspace-private \
  --expect-revision d12bd0b1f5be2f242a1275fd51162f0e46cf5e3b
```

在本次候选上应 exit 1，不是通过。新修复必须使同一用例通过，不能改标点、放宽断言或 xfail；同时保住已有坏推断/诚实缺口/独立事实回归，再跑同一会话续修与最终投影路径。

## 下一步与不要做的

1. 在 **q/research-data-readiness 原整合线**修误删：只撤销错误断言，保可信正文与引用；不能简单扩大“不检查”的范围，也不能只改句法令反例消失。比率正文的同类删除粒度可一并审，但本轮未对它出验收结论。
2. 新业务 revision 重新出完整四叶及 registry 收据，重新独立复核；旧收据不能沿用为新提交全绿。
3. 自然回答质量仍 not_passed。本轮模型调用 0；GLM `glm-5.3-flash` / 兜底 `glm-5.3` 已有用户授权，不再要求统一等待旧 GPT Keychain。固定题目/证据/代码/模型/预算走 conversations 真实入口，不以重采样挑绿。
4. 本轮停止在 T3，不顺手处理 T5、T4/T2、T1 或生产维护。8792、夜跑 wrapper、KB 防写与主检出树均未改。

## 工具与方法沉淀

重复的手动逗号反例已变成带退出码、代码身份和逐项判据的正式 `scripts/review_probes/` 探针；发现的行为洞仍红，未做修复或撤保护绿灯认证。可迁移原则是“错误检测范围和删除范围必须一致，同时测坏内容被拒、好内容保留”，补到既有知识笔记，不新建能力清单。共享 harness-reference 当时工作树脏且领先，未写入，避免覆盖别人的在途搭建。
