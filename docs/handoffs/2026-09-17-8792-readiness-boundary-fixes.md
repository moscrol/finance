# 8792 独立 QC 三类边界返修 · 2026-09-17

## 结论与范围

代码提交 **`6f9df75a6d01c35801dcd7d26b95d2338daf756c`**，基线 `gitea/main@0a1cb8c4`，分支 `fix/8792-readiness-boundaries`，工作树 `~/fwp-wt-8792-readiness-fixes`。

三类 QC 反例已修，并纳入正式 pytest；固定干净代码提交的 Python、前端、E2E、registry 四叶通过，原独立 15 项探针全部通过。**这是候选修复的工程验证，不是生产已修复或真人效果验收。** 本轮未 push / 开 PR / 合 main / 部署，未切判官开关，未触发生产模型请求或改真人用户台账、行情库。交接文档作为后续独立提交，不能将代码收据说成文档新头的全量测试。

起因见审查分支 `docs/qc-8792-readiness-0917@7d253451` 的 `docs/handoffs/2026-09-17-8792-readiness-qc.md`。当时 main 与部署上的 15 项探针各有 9 个失败断言，归并为三类缺陷，不是九个独立 bug。

## 发现、修复与被否方案（按实施顺序）

### F1：明确拒绝登记仍写 checkpoint

原句「不需要登记这只股票为长期跟踪」被旧 `_GAP` 的「只」禁字误伤；长宾语又超过 8 字上限。两个写口与编排层共享同一判据，不是三份正交保护。

| 方案 | 评价 / 结果 |
|---|---|
| 只特判原句、只放开「这只」 | 覆盖不了数量词和合理长宾语，否决。 |
| 无限长度的多个正则 GAP | 中间实现重复「登记」10,000 次约 4.6 秒，存在回溯拖慢，撤回。 |
| 所有研究都不登记 | 会破坏合法登记，否决。 |
| 小句内按词元顺序扫描否定、动作、对象 | 采用；量词与「不要只/仅仅」分开，保留换行边界、疑问/双重否定对照和倒装。 |

`track_contract._opt_out_spans` 复用于 `persistence_opt_out` 与 `parse_track_intent`，研究跟踪意图和持久化意图继续分开：「跟踪一下中际旭创，但不要……登记」仍是研究，但不写长期记录。真实 `ingest_next_watch`、`ingest_flip_conditions` 和编排写入口的测试均落临时目录，含合法登记阳性对照。编排层测试撤掉 pytest 专用早退后执行，不能只测到测试环境保护。

最终单次长输入冒烟：2,002 / 20,002 / 100,002 字符约 0.21 / 1.22 / 5.94 毫秒。仅证明这些构造输入没有复现早期回溯问题，**不是生产延迟、吞吐或严格复杂度证明**；原始读数 `scanner-long-input-smoke.json`。

### F2：未来复查计划被当作证据发布日期矛盾

旧日期门比较句内全部日期与证据语料中的日期集合，无法区分「公告于某日发布」和「计划于某日复查」。

| 方案 | 评价 / 结果 |
|---|---|
| 关掉日期门 | 真正错误发布日期失去保护，否决。 |
| 句中出现「计划」就整句豁免 | 并列的错误事实也会被洗白，否决。 |
| 继续在证据 detail 找到同日就放行 | 无关计划日期会替错误发布日期背书，否决。 |
| 按小句提取明确来源/公告发布日期关系，比较唯一 `source_date` | 采用；无字段、双引、非日历日期等不猜。 |

`_asserted_source_dates` 不把计划、假设、否定、疑问、投产日当发布日期断言；并列的明确错误日期仍拒绝。`llm`（恒通过测试替身）/ `off` 两模式均验保留计划，既有错误发布日期全链测试保持通过。这是**保守机械门**，不宣称理解任意措辞或证明完整事实语义。

相邻缺陷仍独立：`若到2026-10-21需求仍未改善，应重新评估 E1。` 在本分支可能被数值门以 `novel_numeric_condition` 删掉，因为 E1 的编号被当成数量。本轮只对这句测试日期检测函数，不替换数值门伪造全链通过。另一分支 `fix/citation-numeric-gate-0917` 的代码 `2841ce66`（交接头 `3c5f485a`）正在独立处理；本轮未合入、未做组合验证。

### F3：输出排版改变任务种类

冻结 R05 中际旭创题面不变，仅加 `【输出要求】` 或编号，就被旧结构标记当材料，问题/主体丢失，财务研究错路由到 `kol_review`。

| 方案 | 评价 / 结果 |
|---|---|
| 加大 400 字上限、逐条白名单排版 | 下一种排版/更长请求仍会掉落，否决。 |
| 只要出现「请」就全部当用户指令 | 报告内部指令会被升级，否决。 |
| 不再识别粘贴材料 | 会破坏材料身份与权限合同，否决。 |
| 按区域起点区分请求、文档身份，保留真实文档边界 | 采用；输出标签/编号本身不是材料证据，明确请求无任意长度材料化上限。 |

扩展检查补了来源输出字段、请求标题、空行/编号、长问题、问题后紧接真实报告等场景。编号题组识别后不剥走完整请求主体；真正报告仍拆成材料，报告内部的输出要求不升级为用户问题。既有 E2 测试选集通过，但不代签 #770 的跨轮材料合同验收。

## 验证、反证与收据

正式回归：`intelligence/tests/test_readiness_boundary_regressions.py`，共 **84** 个参数化测试实例；禁止 socket 连接、禁真实判官，写口仅临时用户目录。

| 检查 | 实测结果 | 证据文件（审计根下） |
|---|---|---|
| 将同一新增测试文件放到旧基线 `0a1cb8c4` | 68 failed / 16 passed；未修改旧业务源码 | `baseline-red.log`、`baseline-identity.json` |
| 本轮相关模块选集 | 892 passed / 4 skipped | `targeted-final.log`（提交前，非干净提交全量） |
| 撤 `persistence_opt_out` 保护 | 14 failed / 7 passed / 63 deselected | `mutation-opt_out_off.log` |
| 撤日期错配门 | 5 failed / 79 deselected | `mutation-date_gate_off.log` |
| 强制全部识别为材料 | 12 failed / 72 deselected | `mutation-document_always.log` |
| 原 QC 探针，未改判据重放 | 15 passed / 0 failed / 0 errors / 0 skipped | `qc-replay-6f9df75a.json`、同名 `.log` |
| 全仓 Python，干净 `6f9df75a` | **11519 passed / 0 failed / 81 skipped / 2 xfailed / 17 warnings**，544.13 秒 | `full-pytest-6f9df75a.log`、`.exit=0` |
| 全仓 Ruff | 通过 | `registry-6f9df75a.log` 首段、提交钩子 |
| 前端 lint / typecheck / test / build | 全过；Vitest **107 passed** | `frontend-6f9df75a.log`、`.exit=0` |
| 隔离浏览器 E2E | **34 passed / 2 skipped** | `e2e-6f9df75a.log`、`.exit=0` |
| registry 五项 + runtime catalog | 全过；crosswalk 98 条反向 warning，不是 error | `registry-final-6f9df75a.log`、`.exit=0` |
| 固定 revision 的测试收据校验 | 八项通过，base drift=0 | `receipt-check-6f9df75a.log` |

全仓收据：`~/.finance-runtime/test-receipts/20260917T134635Z-6f9df75a.json`，原样副本也在审计根。Python 用主树 `.venv-workbench/bin/python`，`env -i` 保留 PATH/HOME/KNOWLEDGE_WIKI，`umask 022`。不要看共享「最近收据」指针：别的 agent/变异测试可能覆盖它；本收据在收尾时重新按完整 revision 校验通过。

E2E 用 8793/8795，`RE06_E2E_URL` 同步指向 8795；用户目录、测试 DuckDB、fixture 仓与真人生产隔离，模型密钥清空。两项跳过是绑定链只跑 desktop、tablet/mobile 不重复。服务随测试正常退出。它验证浏览器/API/持久化集成，**不是金融题的真实模型质量测试**。

前端离线装包因清缓存后缺 `dompurify` tarball 退出；随后 `pnpm install --frozen-lockfile` 下载固定锁文件依赖成功，锁文件无改动。首次 registry 串行命令在四项通过后误调用不存在的 `build_runtime_catalogs.py`，exit 2；找到真实 `gen_runtime_catalog.py` 后补齐 crosswalk 并重跑完整集合通过。初次失败日志保留，不能只摘前四行冒充首次全绿。

## 证据位置与复跑入口

- 原始审计根：`~/.finance-runtime/reviews/8792-readiness-fixes-20260917/`。
- 仓内索引：[verification/2026-09-17-8792-readiness-fixes/README.md](../verification/2026-09-17-8792-readiness-fixes/README.md)。源码/日志哈希见同目录 `results.json`；原日志不塞进 Git。
- 旧基线重放树仍保留在审计根 `baseline/`；仅新增一个未跟踪测试文件，与提交版逐字节一致，不当成干净旧版本全仓验收。
- 未产生新的通用工具：承重检查正式进入 pytest；重放复用原 QC 脚本；三次进程内变异的复现命令在 verification 文档，不修改磁盘源码。关键词共现不等于语义关系的取舍留在本项目决策与正反例，不扩成另一套自然语言解析框架。

## 共享记忆维护检查（不混入代码门禁）

项目索引与能力图谱已回写，由共享记忆的既有自动同步提交 `2524bcdf` 收录；只含本轮两个目标文件，未手动改其他笔记。图谱校验通过。额外执行 `vault_lint.py` 为 **19 errors / 17 warnings**（死链、旧笔记字段、TOOLKIT 镜像漂移等），**不能报告记忆库整体全绿**。

为区分本轮引入与存量问题，用当前库的同一文件清单/校验逻辑，仅在进程内将两个改动文件的读取替换为父提交 `673594fa` 原文重验：前后均19项错误、错误集合逐条相同，无新增/消除；这不是完整历史仓快照验收。见审计根 `memory-lint-comparison.json`、`vault-lint.log`、`vault-lint-baseline-overlay.log`。不为本任务顺手更改其他agent的笔记或脏的harness-reference仓。

## 后续与禁止外推

1. 下一任先核对最新 main，独立复核本提交；需要提交到远端时显式指定分支，勿把 upstream 的 `gitea/main` 当推送目标。
2. 合并/部署需用户另确认，按 acceptance-workflow 验最终整合 revision；候选收据不借给新合并树。若与 citation-numeric 或 #770 整合，重新跑冲突检查及组合回归，两者都触碰 semantic verifier。
3. 获授权后从隔离 Workbench 真入口压三类边界，不把浏览器 fixture 或测试替身当真实模型证据；冻结模型、代码、判官模式及数据截止日。
4. 判官 `off` 启用与观察期、#770 材料整合、行情新鲜度、RE06/#53 真人效果分别处理。本轮没有替它们签收。
5. 8792 只读复查仍 healthy、`bf662e9310ff`、dirty=false、matches=true；启动器仍未设 semantic judge（默认 llm），evidence judge=auto。产品门页与 #55 收据路径已纠正，不因此改变开关或公开 schema。
