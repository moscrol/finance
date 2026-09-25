# #868 前向到 09-25 main 的组合离线门禁

## 结论与身份

本轮交付的是新的组合候选及作者/工程证据，不是生产研究质量、独立审查双轴闭合或发布许可。未新增付费模型请求，未启动 L6，未合 main，未部署或改动 8792。

- 工作树：`/Users/a77/fwp-wt-pr868-current-0925`；分支：`baseline/pr868-current-0925`。
- **受测代码**：`fb41cebdaa6a186c14bd402f0f2dd83705f64421`。
- **固定基座**：`fe9fdbfd70a637efc5bcf0cfecf74080a8d6a90c`；合入上一轮组合交付 `23536eb9aea1ab43551185537715a0c7365df242`。#868 owner、#910、#911 均为祖先。
- 解释器：`/Users/a77/fwp-wt-pi-research/.venv-workbench/bin/python`，Python 3.12.13、httpx 0.28.1，依赖指纹 `66726d345bf37ce5`。
- 证据原根：`/Users/a77/.finance-runtime/reviews/pr868-current-20260925/`；成功批：`attempt02/`。
- 仓内归档：[manifest](../verification/2026-09-25-pr868-current-offline/manifest.json)，60 份原件按字节复制，另存逐例差异。脚本按 `.py.txt` 存档，不作为新的运行时入口；完整大 JUnit 保留在原根并记哈希。
- 本文件及归档属于后续 docs-only 交付。**完整工程收据只绑定 fb41，不自动绑定包含这些文件的新 HEAD。**

## 发现与处理顺序

1. main 已包含 #920 的 `LLM_COMPAT_PAYLOAD`，在五个 `_post_chat*` 调用点改写请求字段，另有 RAG 等改动。旧 adbe 收据不能说明组合兼容性，因此在自有干净树前向；不动 owner 分支、主检出树、封存批或共享环境。
2. 合并只有 `scripts/review_probes/run_extraction_mutations.py` 的 docstring 套件示例冲突，保留双方并集。产品代码自动合并，本轮没有手改产品实现。pre-commit 通过；代码地图 build 命令曾超时，后续 status 确认 ready、34209 nodes、绑定 fb41；不把 ready 当架构完整或生产可用。
3. 在新证据根回放封存 C3 探针。原件把 `list.append` 作为 observer，无法接收 `status=` 等关键字，及时与迟到用例均出现 TypeError；不是 provider 组装失败。原封存文件未动。
4. 第一轮只修回调后，行为本已符合截止窗口，但本轮包装器错把最终 `_JudgeCall.exc_class` 当实际请求异常，断言失败。完整首轮日志保留。代码合同把最后的零预算槽和已发出的失败请求分开：最终槽 attempt 1、timeout 0、exc_class None；真实 attempt 0 的 `LLMDeadlineExceeded` 在 `last_dispatched_failure`。
5. 在 `attempt02` 新副本补读已有字段，包装器按原合同收紧为 0.8 秒窗口加 0.2 秒容差，重新执行。及时对照 0.077681 秒，1 请求，headers/eof/closed，报告收到且账本 success；迟到对照 0.803296 秒，1 请求，headers/closed，报告未收到、unavailable=true、账本 failed/timeout，根剩余 9.599994 降至 8.776075。最后零预算槽不算另一笔已发请求。
6. 跑新候选四类工程叶子并核验完整收据。准入阈值仍是 load<8、空闲盘≥20GiB、精确 revision/干净树和测试端口可用；有资源拒绝就等新观察，不抬阈值。它是离散采样，不是全程资源隔离或全局锁。
7. 另补启用 `LLM_COMPAT_PAYLOAD` 的五调用点作者检查：5 个及时对照、5 个共享截止、2 个流取消，共 12 子例。实际 loopback 子进程 HTTP；每例 1 请求，字段改写与共享 deadline 身份均核验。10 秒 call slice 下，0.5 秒共享截止实际 0.5023–0.5325 秒停止；取消触发到停止分别 0.00931、0.00644 秒。只是单批观测，不做性能趋势推断。
8. 内层沙箱证据保全首次因 pytest 截短临时目录名而未匹配到文件；只停自有保全进程，改为按 sandbox 布局定位，未动测试进程/断言。四份原始 JUnit 与两份 C3 字段记录均在清理前保存。
9. 运行期间 owner 在另一会话获批执行旧 f261 的 C3-only 独审，另见下节。本轮同步读取事实，不继承其预算或签字。main 又前进至 `4db9a42b69b0d30bcf55b2eafb64151a6c1bb317`，仅改两份文档；没有中途更换受测候选或把固定基座校验冒充 latest-main 校验。

## 新鲜工程读数

| 范围 | 结果 | 原根内凭据 |
| --- | --- | --- |
| workspace doctor | ready，exit 0 | `attempt02/doctor.log` |
| registry parse/check/tables/views + ledger crosswalk | 五项 exit 0 | 对应 `registry-*.log`、`ledger-crosswalk.log` |
| frontend install/lint/typecheck/test/build/e2e | 全部 exit 0；单元 123P；浏览器 34P/2S；identity_stable=true | `attempt02/frontend/frontend.json` 及各叶日志 |
| Ruff | 通过 | `attempt02/python.log` |
| 全仓 Python | **16243P/0F/0E/75S/2X/0XP，collected=16320**；1771.02 秒 | `attempt02/receipts/gate-kjCOgwV8/pytest.json`、完整日志及 `attempt02/python.xml` |
| 完整收据校验 | exit 0；revision、解释器、依赖、干净树、完整收集面对账成立；固定 fe9 漂移 0 | `attempt02/receipt-check.log` |
| 五调用点字段改写/截止/取消 | 12 作者子例通过 | `attempt02/compat-author.log` |
| C3 原探针接口负控/修正后行为 | 原件按预期 exit 1；新副本及时/迟到两例 exit 0 | `attempt02/c3-{original,corrected}.log` |

没有 `-k`、mark、ignore 或 deselect 收窄全仓范围。相较 adbe 的逐例对账：**新增 261 例、删除 0 例、原 BP 13 例从 skip 转 passed**，不是把旧计数相加。详见 [junit-comparison](../verification/2026-09-25-pr868-current-offline/junit-comparison.json)。

同一份完整 JUnit 中，research conformance 36P、Workbench in-process API 20P、Pi review repair 73P、timeout diagnostic 35P、main-gate receipt 66P，无 nonpass；它们不是额外批次。内层两个沙箱轴各 C3 3P/C7 66P，亦不重复相加。迟到 C3 分别约 0.8144/0.8061 秒，headers 已到、报告被拒、根预算扣减；窗口耗尽与根耗尽原始记录也保留。

75 skips：缺真实行情库 57、跨仓 KB 配置 4、嵌套边界声明 4、参照桩不适用 3、已有地图场景 3、真实 SDK opt-in 2、缺历史 tmp 冲突源 1、缺 `tdxpy` 1。两个既有 xfail 是 Codex 无 resume 的修复收据缺席，以及 KOL 示例与路由 pattern 不匹配；本轮未修复，也未宣称关闭。

浏览器两个 skip 是绑定链场景只在 desktop 执行，不能说三个视口都独立执行了该场景。脚本化来源/API 持久化覆盖不能证明真实金融来源、自然自主研究或 L6。

协调器终态 completed，所有步骤按其 declared scope 接受；原探针故障作为预期负控不是“全部 exit 0”。Python 子进程 exit 0、无 timeout、组清理 already_absent，总墙钟 1803.48 秒。监督/测试/保全进程均已结束，19981/19984 无监听，成功 basetemp 已清理，原根约 2.9MiB。未碰共享 19899 路由、生产监听器或旧预算。

## 旧独审的新事实及边界

[owner-c3-readback](../verification/2026-09-25-pr868-current-offline/owner-c3-readback/readback.json) 是只读快照。另一会话获批后，旧 f261/base033 的 C3 spec report 为 PASS，仅 C3 verified；其他 C1/C2/C4–C7 都明确 out_of_scope。host 三次复跑及放宽窗口对照后作有限采信，并跨旧批汇总称 f261 的 spec C1–C7 已验证、零产品发现。

该批新增 18 请求、累计 333/354 是**它的**审计，不是本轮可用余额。本轮付费请求为零。其 C3 探针直接设置 `_active_policy`、patch provider chain，属 `_run_judge_once` 单元层，不是整条 Episode；报告允许 0.6 秒调度容差，虽然实测约 0.805–0.810 秒，不等于其断言强制了原 0.2 秒容差。

不能因此覆盖旧 quality 轴 `PASS_WITH_LIMITS`、C7 先前未验项，或把任何旧批结论改签 fb41。封存 next/spec 的原 CHANGES_REQUIRED 保持不动，新批补证是追加历史，不是改写原报告。**fb41 当前没有独立审查收据，也没有 L6 自然金融验收。**

## 决策与被否方案

| 选择 | 否掉的方案 | 原因 |
| --- | --- | --- |
| 固定新组合重跑全仓及前端 | 继承 adbe 或旧 f261 读数 | 新 main 改实际 HTTP 调用点及其他运行时；修订与依赖必须绑定 |
| 修作者探针/断言，保留首轮失败 | 按错误探针去改生产异常或覆盖日志 | 接口和聚合槽理解错不等于生产缺陷；要能追溯哪一层出错 |
| 同时读最终槽与 last_dispatched_failure | 只看最终 exc_class | 否则把未发出的预算拒绝误当真实失败请求，或误计费 |
| 按布局收集内层原件，哈希归档 | 从外层 4P 推断内层覆盖，或依赖未截短测试名 | 外层数量不能表达内层断言；pytest 会截短临时目录 |
| 保留封存日志，公开格式红 | 修剪旧日志换 diff-check 绿 | 审计字节应保持原样；保护证据不等于格式豁免 |
| 只准备新补审提案 | 运行旧 c3/generator 或借旧余额 | 候选、基座、解释器、输入、授权均需重新绑定 |

工具沉淀：复用现有 `_run_logged_command`、`diagnose_llm_timeout` 的真实 loopback fixture 和 receipt checker，没有引入第三条生产 loop、新调度器或新传输抽象。一次性协调/保全/归档脚本只服务固定 SHA 和证据根，源码随归档保存；没有把绑定本批目录的脚本包装成通用产品工具。可迁移的是“聚合终态与最后真实尝试分账”的证据读取原则，写回共享知识笔记。

## 后续与禁止事项

1. owner 选择并冻结真正要继续的组合候选。不要直接把旧 repair generator 的历史配置启动成新批。
2. [新独审提案](../verification/2026-09-25-pr868-current-offline/review-plan.md) 尚未获批：新根、spec/quality 串行，每轴 4+17+17+1=39 请求，总上限 78；不借旧余额、不自动重试或增额，逐轴保留 limits。若最终候选不是 fb41，先重绑身份和适用性。
3. 独审后另批 L6 自然金融验收；冻结模型/数据，检查实际来源、子研究、反证、修订与完整 Episode 审计。工程和作者 tests 不代替它。
4. 真正集成时核对最新 main 和 INDEX 的并发文档变化，取得当时 revision 的门禁与用户合入许可。部署 8792 另批，保留回滚并核对 live identity。

完整 `git diff --check fe9..fb41` 仍 exit 2，涉及 8 份继承封存文件；逐字节与 owner `89624eac7e76` 相同。排除整个旧 verification 区域后 exit 0，但这**不是**全 PR 格式检查通过或豁免。完整文件表见 `attempt02/format-audit.json`。新增归档的 `attempt02/format-check.log.txt` 逐字保存了这些告警，另有三份 `frontend-{1,2,3}.log.txt` 原件带文件末空行；因此本次 docs-only 暂存差异的 `diff --check` 也 exit 2（4 份原始日志），未修剪、未豁免，不能说新增差异全绿。本轮不关闭 #868/#910/#911、不去掉 WIP、不改变生产或付费边界。
