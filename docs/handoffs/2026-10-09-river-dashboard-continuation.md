# 2026-10-09 长河 / Dashboard 接续执行与验收

## 裁决

**本地工程门禁通过；可接续、不可据此发布批准。** D4 公开查询范围/资格的模型输入合同已修，完整端到端与响应式检查已执行；大联合材料容量、首屏、真实金融解释及归档补全仍有明确边界。未推送、未合主干、未部署、未写生产、未主动调用真实模型。

## 身份与证据

- 工作树：`~/fwp-wt-river-dashboard-fix-1009`，分支 `fix/river-dashboard-evidence-1009`。
- 接手文档：`a6985d0fbdda3c4e56822ba294a8b1411fb6c9ca`。
- D4 实现：`3204827ea47e2d59c7f7a2c41c80f8629abc97b5`，只提交两处服务与两处测试。
- 干净最终受测候选：`50013acd6227862b0319efc43fae568191c77d45`，相对 D4 实现仅修复复盘证据 E2E 的一行直接子 summary 选择器。
- 本文与在途交接的后续文档 tip 另计，不把候选收据移签到文档提交。
- 固定基座仍为原联合候选；未 fetch、未整合当前远端主干，因此不是最新主干集成批准。
- 新私有证据根：`~/.finance-runtime/reviews/river-dashboard-continuation-20261009-arena/`。
- 前轮 `river-dashboard-fix-20261009/` 的原 55 件保持不改；前轮 21,703 Python / 241 前端读数仍绑定 `b4062d55b927…`。

## 根因、对象合同与取舍

普通准备消息包含 typed D4 `query_basis`，grounded 路径却重建模型消息，只读取 AnswerSpec claim registry，未继承准备消息的范围后缀。修复在内存 AnswerSpec 保存不可变公开元数据，再把它作为一行原子元数据纳入相同 12,000 字符窗口。它不是新的 claim 或 EvidenceAtom 许可，也不进入公开 AskResult 事实台账；不解析生产者文案、不重新读库、不改原生 Episode / owned 语义。

首答、补写与判官输入共用该 registry。typed D4 事实若失去范围则拒绝调用；送达视图拒收缺少、重复、改写范围的记录。JSON 资格保持 `true` / `false` / `null`，不能利用 Python 的 `False == 0` / `True == 1` 偷换类型。省略计数仅数 claim，不把元数据当作 claim。

预算不可混用：12K registry 字符、48KB 外层原子预算、24K 开场日卡预算均未上调。D10 仍是完整单块推断，未截历史表、未升级为事实；提纲与确定性校验仍只对送达子集成立。

### 不能隐藏的容量边界

接口替身而非真实模型测得：

| 场景 | 可用 / 送达 D4 | registry 字符 | 模型回调 | 结论 |
|---|---:|---:|---:|---|
| D4-only | 3 / 3 | 5,798 | 1 次脚本化回调 | 完整 D4 范围与三态资格均在实际接口输入 |
| 原大 D4+D10 样例 | 3 / 0 | 无，准入拒绝 | 0 | 完整范围与材料装不下，不能静默丢元数据 |

D4 公开范围行 2,324 字符，完整 D10 行 11,216 字符，再加最短完整 D4 支持行及换行，最低 14,092 > 12K。前轮 11,967 字符的“最低 D4 席位”不能沿用为本轮完整资格送达证明。较小、保持完整推断块的合成联合样例通过回归，但不替代大样例，也不证明模型实际利用或金融质量。

## 新候选上的实际验收

| 验收 | 实际结果 | 原件 |
|---|---|---|
| 全仓 Python | 21,722 passed / 78 skipped / 2 xfailed / 0 failed / 0 errors；收集 21,802 | `test-receipts/python-final/gate-O3gd6fTT/pytest.json`、原始日志 |
| 收据身份 | 干净同 SHA、解释器 Python 3.12.13、依赖指纹、未绕依赖门、收集面未收窄均通过 | `evidence/final-receipt-check.log`、`final-verification.json` |
| 全仓 Ruff | 通过 | 最终 Python gate 原始日志 |
| 前端 lint / typecheck / build | 全部退出 0，首尾同 SHA 且干净 | `validation-final/frontend-main/frontend.json` |
| 前端组件 | 25 文件 / 241 passed | `frontend-3.log.txt` |
| 主 Playwright | 52 passed / 2 既有 skipped / 0 unexpected / 0 flaky | `validation-final/e2e-main.json` |
| 连板日历专项 | 6 passed，desktop / tablet / mobile | `validation-final/e2e-calendar.json` |
| 复盘证据专项 | 9 passed，desktop / tablet / mobile | `validation-final/e2e-review-evidence.json` |
| 数据与指纹边界 | 无效报价待核；有效封板/断板对照；窗外比较归档变化拒收旧指纹 | `evidence/boundaries-and-real-coverage.json` |

主配置排除两个专项，故必须分别执行，不能用主套件代表所有 E2E。新的 499 项定向回归、红→绿日志保持其原提交前身份，不冒充全仓收据。registry 五项检查均退出 0，台账反向 101 个 warning 未清。

## 视觉检查：完成检查，但未签“首屏通过”

本轮使用用户明确授权的临时无账号浏览器，仅本地合成夹具。真实归档 API 和页面数据投影运行，只有独立市场导航按既有 E2E 夹具替身。四种尺寸均无页面横向溢出、无脚本错误、无非 GET 请求；读法默认折叠，读数先于读法，展开和解读说明可操作。截图和测量在 `visual/`。

| 尺寸 | 读数区顶部 y | 首屏结论 |
|---|---:|---|
| 1440×900 | 约 695 | 顶部出现，完整卡区仍需滚动 |
| 1024×768 | 约 695 | 只出现顶部，完整卡区仍需滚动 |
| 390×844 | 约 954 | 首屏外 |
| 1280×625 | 约 695 | 首屏外 |

因此不能把 DOM 阅读顺序正确、E2E 通过签成首屏设计通过。未擅自删去日期/缺数说明、合同或进一步改版。视觉只证明响应式与操作边界，不证明真实行情或金融解释。

## 真实归档覆盖：只读复核，未补档

2026-09-03 → 2026-10-08 固定 20 个计划交易日，仍仅 10 日有 readable daily-review；10-08 缺 daily-review。24K 日卡窗口实际交付 9 日、23,457 字符，09-16 因篇幅省略，不是无数据。缺档不能用别日、daily-agent 或推断补成事实。读取前后实际 daily-review 导出哈希一致；不排除其他并发写者在该时段之外更新。

## 失败原件与环境归因

1. 第一次主 E2E 平板前置步骤超时；电源日志证实 14:24:18 合盖休眠 608 秒，14:34:26 唤醒，和约 10.1 分钟 trace 间隔一致。原失败收据与 trace 保留；同候选该用例 3 次复测通过后，另起目录跑完整门禁。未加大超时或抹掉原失败。
2. Node 26 缺 `corepack` 导致专项服务未启动。仅在本轮私有 PATH 放转发器，先验证 `packageManager` 与已装 `pnpm 10.12.1` 一致，不装全局、不改配置。Node webstorage 用 `--no-experimental-webstorage`，不删异常用例。
3. 专项实际执行后 9 红共用前置 locator：外层 `details` 的 descendant `summary` 匹配 8 个标题。`50013acd…` 只改为直接子 `:scope > summary`，原断言与功能场景保留。
4. 首轮全仓 Python 21,721 passed / 1 failed：代码地图倒排索引指向不存在 nodes 行。刷新图仍复现后，备份本地缓存，用 SQLite 官方 FTS `rebuild` / `integrity-check` 从真实 nodes 表重建；nodes 数量和 daily-full 节点不改。探针 44 passed / 3 conditional skipped 后重新跑全仓，原红收据保留。未删图、跳过探针或造节点。
5. 解释器不得 resolve 可执行文件 symlink 成宿主 Python；本轮一次验证准备失误日志保留，测试最终始终使用本树 `.venv-workbench/bin/python`。

## 发布与剩余工作

本地完整工程通过不等于已通过 GitHub Actions、已集成最新 main 或已部署。新真实模型请求 0，旧 GLM 金融质量未通过裁决保持原样。

下一步需决定：大联合材料的结构化无损准入方式、首屏顶部空间是否继续压缩；独立授权真实模型首发、利用与正确性验收；另行授权真实归档补全。发布操作须用户确认且完成适用远端门禁。自然时钟协议截止日夹具风险未修，不借本次自然时钟通过宣称已解决。

## 晚间接管指针

以上是下午固定50013候选的历史状态。已补齐原私有证据根的REPORT、completion和199件完整性清单；后续修复与当前准备状态见[晚间接管快照](2026-10-09-arena-session-takeover.md)。原50013的收据不移签到后续修复。
