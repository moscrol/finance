# Adaptive research：#830 前向合流与三项遗留收尾

## 背景与范围

接手分支 `feat/adaptive-research-loop@cb47cc3b6`，树 `~/finance-worktrees/adaptive-research-loop`。接手时该树干净，主检出树有其他任务的大量改动，不在本轮处理范围。原分支领先 `gitea/main` 33、落后 5；旧全量收据 `20260921T092038Z-ba8c55c3.json` 只签 `ba8c55c35`，不能证明合流后的代码。

本轮只前向合入 main、运行工程门禁、校正并压缩交接；没有增加业务补丁，没有再次调用 K3/GLM，没有推送、开 PR、合回 main 或部署。自然模型的未闭合项没有因工程门禁通过而升格。

完整的接手历史仍可从固定提交读取，不用靠当前 inflight 找旧细节：

```bash
git show cb47cc3b6:docs/handoffs/inflight/feat-adaptive-research-loop.md
```

该历史文档包含已过期状态及相互矛盾的旧段落，仅作过程原件；当前结论以本快照与本分支 inflight 为准。

## 按发生顺序

1. 在干净的分支树前向合入 `gitea/main@f2c3e9e1a24f`（含 #830「K3 写手兼容与无判官独立性统计」），产生 `c07dda427608d694a905cc635b15f8ee932ad48c`。无冲突，门页自动合并。没有合回 main。
2. 最早两次定向命令误在主检出树执行，产生 `20260921T094727Z-b4a35fa2.json`、`20260921T094750Z-b4a35fa2.json`，均是找不到目标测试、零执行；主树 Ruff 所报 `scripts/check_daily_plan_local.py` 也不属于本分支。以上不能当本片失败或通过证据，未修那些无关文件。随后在目标树使用相对 venv 路径也失败，因为它没有本地 venv；改为显式工作目录和主树解释器。
3. 在 `c07dda427` 上 Ruff 通过，#830 新增两套测试 42 passed；完整 pytest `12678 passed / 87 skipped / 2 xfailed / 17 warnings`，exit 0。没有再现前一会话的 SQLite disk I/O error。
4. 原始前端四项全过；首次 E2E 因自动回落宿主 Python 3.14、缺 uvicorn，在启动服务前失败。显式指定共享 workbench 解释器后 34 passed / 2 skipped。没有改 Playwright 配置。
5. 用户要求继续后再次 `git fetch gitea main`，主线仍为 `f2c3e9e1a24f`。核对原始 K3 README，发现旧交接把逐项变体结果概括过头，并曾把 content 泄漏写成已兼容；本快照纠正这两点。
6. 为得到前端正式收据，先把本轮尚未提交的 inflight 草稿和 diff 备份到树外，仅还原这份自有文档，恢复精确干净的 `c07dda427`。使用仓库现有 `scripts/run_frontend_gate.py` 顺序重跑六步（含安装和 E2E），首尾身份一致、树干净、全部 exit 0。端口 19961/19964，未触碰生产 8792。
7. 同一干净提交再跑 Ruff、registry-check 四项、spec↔台账对账和 Python 收据校验，全都 exit 0。注册表仅校验本仓，缺席跨仓项 23 个跳过；台账反向 98 行仍是 warning，不宣称全仓零警告或跨三仓通过。
8. 最后仅写本快照和短 inflight。文档提交后的 HEAD 与被测 SHA 不同；收据不得移绑新 HEAD，更不代表未来合回 main 的结果。

## 三项遗留的最终处置

### 1. 自然模型“无工具修复 + 自报 partial”：仍未闭合

K3 可达不等于能稳定完成多调用 episode。原始抓包、两份拒绝请求、响应和代理在：

`~/.finance-runtime/k3-gateway-intermittent-400-20260921/`

复现代理是该目录的 `capture_proxy.py`，不是需要从 `/tmp` 找回的未封存文件。复现时按原件 README 取钥，不把密钥写入交接或提交。

**原件 README 的三次重放表**：

| 变体 | 原件结果 |
| --- | --- |
| 同一 96 KB 请求原样 | 200 / 400 / 200 |
| 去 temperature | 200 / 200 / 200 |
| temperature=1.0 | 200 / 200 / 200 |
| 去 schema additionalProperties | 400 / 400 / 400 |
| user 正文截到 2000 字 | 400 / 200 / 400 |

所以不能写“每个变体各三次全部混合”，也不能用这些少量试验认定稳定的 50% 拒绝率。**同一字节载荷既成功又失败，排除了它必然因固定请求形状非法而被拒的解释；不能据此认定每个字段在所有上游实现上都无影响。** 现有证据定位到网关/上游路径的不稳定，尚未精确到内部哪一跳。

#830 对 K3 的 temperature 兼容策略与这个结论可并存：本轮保留已合入的策略，没有撤掉兼容，也不把它当作间歇 400 已修的证据。没有合流后新的 K3 请求，因此不能宣称当前网关恢复或仍有相同失败率。

无 id tool_call 有运行时合成 id 补位；推理正文漏进 `content` 则是已观察到的协议瑕疵，可能增加 steering（引导模型按协议重答）轮次，**不是本轮已修项目**。

同题修复版 GLM 三次均自报 completed，故未覆盖目标分支；不继续刷次数碰运气。HTTP 400 维持不可重试语义，不因单个上游异常改变全局重试规则。闭合需要网关恢复后的稳定 K3 或稳定第二模型，并自然观察到目标路径；离线强制分支不能冒充这个证据。

### 2. 删句残片：不做已接受正文的外科手术

维持上一会话决定：宿主不剥改已接受句的连接词。此前候选对“但丁 / 相反的观点 / 同理可证 / 所以说”误剥；公开 partial 提示已经承认本轮有表述未通过核验。数字门修复后的同题一次复验删句 6→1、没有悬空列表项，只支持源头误删收窄，不证明所有残片已消除。若仍频繁出现，先量化再决定逐词分档规则，不先写统一词表。

### 3. 股票代码：已修，不称自动归一

`d9e2875c0` 对 `stock_ts_code` / `sector_ts_code` 这类列的 eq/ne/in 精确比较拒绝裸六位码并提示后缀族；没有替模型猜交易所。B 股等例外使自动猜测可能查到错误标的，拒绝并给重试提示比静默空结果或猜错更可靠。`contains` 裸码仍可用。

前序证据为撤掉该闸时 7 条中 4 条红、相关三套 504 passed / 16 skipped；本轮在合流后的完整 Python 套件再次覆盖，不把前序撤线写成本轮重做。

## 保留的实现决策

| 选择 | 被否方案 | 原因 |
| --- | --- | --- |
| 修复轮改了 draft 或 bindings 就重新核验 | 因 repair_model_stop 而跳过新稿复核 | 停止下一轮与允许公开哪份稿不是同一判据 |
| 复核赶不及时按旧稿发布、压 partial 并说明未复核修订 | 发布未经核验的新稿或只给内部 stale 标记 | 公开状态必须解释实际发布版本 |
| 不改 admit_repair_result 进度门 | 将所有无工具 partial 当成进展 | 会牵动预算和轮次，非本次发布保真问题 |
| 只对结构化观察值作单位量级匹配 | 放宽所有 detail 裸数 | 日期和序号不应获得单位背书 |
| HTTP 400 仍不重试 | 因网关间歇拒绝扩大客户端重试 | 不让上游异常改写客户端请求错误语义 |
| 冻结业务 SHA 留证，文档单独提交 | 给文档 tip 移绑旧收据或补造首尾观测 | 测试证明的是实际执行过的那棵树 |

原修复实现 `00d35ae80` / 钉子测试 `9e08b6b39`，六类撤线日志 `~/.finance-runtime/adaptive-fix-mutations-20260921.log`；首次 zsh 分词错误的无执行记录及重跑均保留。更多背景见同目录 `2026-09-21-adaptive-repair-publication.md`、`2026-09-21-adaptive-repair-delivery.md`。

## 收据与工程边界

**以下均签 `c07dda427608d694a905cc635b15f8ee932ad48c`，不是随后文档 tip。**

| 叶子 | 结果 | 原件 |
| --- | --- | --- |
| Python 全量 | 12678P / 87S / 2X / 17W，exit 0 | `~/.finance-runtime/test-receipts/20260921T100727Z-c07dda42.json` |
| Ruff | exit 0 | 下述目录 `ruff.log` |
| K3/判官离线接缝 | 42P | `~/.finance-runtime/test-receipts/20260921T094836Z-c07dda42.json` |
| 前端 lint/typecheck/test/build | 全过，110P | `frontend-c07dda427/frontend.json` 及逐步日志 |
| 浏览器 E2E | 34P / 2S | 同一前端收据及 `frontend-5.log.txt` |
| registry-check 四项 | 全 exit 0，仅 ws 在场 | `local-checks.json` 及 `registry-*.log` |
| ledger-spec-crosswalk | exit 0，反向 98 warning | `ledger-crosswalk.log` |
| Python 收据校验 | 精确 revision、依赖、干净代码、基座漂移 0 均过 | `pytest-receipt-check.log` |

新证据根：`~/.finance-runtime/adaptive-forward-830-20260921/`。前端收据 `complete=true / identity_stable=true / dirty=false / exit_code=0`，每步日志包含 SHA256。未借用共享 `latest.json`（其他会话会覆盖它）。

前一会话同 revision 的 SQLite 红日志仍保留原位，本轮未删除，也不改写成绿；本次工程通过不替代自然模型质量、独立 Spec/Quality（规格/代码质量）审查或生产验收。

## 接手动作与不做项

- 原始 live 目录 `adaptive-live-smoke-20260921-q2-fix/`、`-q3-fix/` 与 K3 目录保留；查旧冒烟先看各自 README/SHA256SUMS，不重新拼题或改原件。
- 后续若要推送/PR/合并，先取明确授权，重取 main 并为最终待合 SHA 收集所需门禁，不拿本快照声称后续 main 已通过。
- 不为碰目标状态词刷模型次数；不恢复悬空连接词剥离；不猜交易所后缀；不放宽 400 重试；不动生产或他人工作树。
- 本轮无新增临时排查工具，复用现有 frontend gate 与 test receipt checker。工作目录/解释器错配已被现有绑定身份的门禁识别，未另造第二套工具；本轮没有新 runtime 门禁改动需要回写 harness-reference（其共享树仍有他人未提交内容）。
