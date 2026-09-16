# 日期快照：能力放大 / 工具线下午推进（2026-09-03b）——web 链路首读、P2 第一步、子代理 spec、工具沉淀

配对的在途交接：`docs/handoffs/inflight/spec-capability-amplification-output-gate.md`。上午的快照
`2026-09-03-capability-line-session-handoff.md` 写到 #549；本篇接着写。不限长、写完不改。

## 0. 不读这段会误判后面每个决定的背景

- 接手时的委托：上午交接的「下一步」六条 + 三项待用户拍 + 工具沉淀候选两件，用户一句「你来执行」。
- 8792 全天在 `c88c81da5120`（0903d，另一会话切的）；**本篇没有切流**，下面五张 PR 全部未合入、等用户确认（AGENTS.md 合入须确认）。
- 运行快照给 live 用：`~/.finance-runtime/finance-workspace-8864e92d2592`（detached，含 web_search 修复），8792 不动。
- main 在本篇中途从 `78fb8639` 前移到 `c19f7594`（#554，另一会话压缩 `inflight/main.md`）；五张分支对新 main 冲突探测全净。
- 并发：#554/#555/#556 是别的会话开的（inflight 压缩 / 复盘 JSON / 额度账本），没有碰同一文件；`fwp-wt-rag-window` 里他人的 `rag_worker.py` 未提交改动全天未变。

## 1. 按发现顺序做了什么

1. **核实交接**：main=78fb8639=#549，两份文件字节数与交接一致；读 spec 全文、AGENTS.md、handoff skill、看板。
2. **① 开跑前先离线直调 `fetch_web_search`**（怕烧配额换来「web 无结果」）：五道题全回实体官网导航页/无关页，`status=success`。
3. 直连 CDP 代理逐 0.15s 采样：页面标题与搜索框是完整查询，`li.b_algo` 10 条却是壳；~2s 后 `href` 变 `&rdr=1&rdrig=…` 重载，才有真结果。`_G.JCache=1` 前后不变 → 不能当判据。
4. 顺手发现 9222 的 Chrome for Testing 是 `--headless=new`，UA 带 `HeadlessChrome`。改 `~/scripts-local/chrome_debug_agent.sh` 加 `--user-agent`（可 `CDP_USER_AGENT` 覆盖/还原），`launchctl kickstart -k` 重启（先确认无 daily-full/fupanhui 任务、只开着 newtab）。**改完仍拿壳**——UA 不是根因，解析时机才是。
5. **修 `web_research._fetch_web_search_uncached`**：`/eval` 一次带回 `{href, ready, items}`；只在 `rdr=1 && complete` 收；无跳转时结果稳定 3s 才收；deadline 未稳定标 `unsettled`；`/eval` 形状错 → `parse_error`；轮询 1.0s→0.3s。首版多写一个 `}` → 代理 4xx → `request_error`，桩测试看不见 → 抽成 `_bing_page_state_script` 加括号配平钉子。5 钉 + 变异 3 红。live 复测：腾讯 6603 亿 / 小米 3659 亿 / 平安 IR。
6. 会话跑热约十分钟后 Bing 不再跳转、首屏即真结果 → 兜底路径被 live 用到，证明它必要。
7. 整仓门禁 7574P/**6F**：多出 `test_tool_hidden_for_too_small_window_is_the_same_machine`。基线树同样 6/6 红 → 不是本改动；`would_grant` 14.999 vs 15.0 是两条 loop 各建 deadline 的墙钟差。开第二棵树 #551 改容差比。**后来在 #557 树的整仓跑里它是绿的**——确证是抖动。
8. **工具沉淀先做**（因为马上要开四张 PR）：`scripts/gitea_pr.py`（open 按 head 查重 / conflict-check 走 merge-tree / token 只从 Keychain / merge 须 --yes）、`scripts/run_main_gate.sh`（拒脏树 → ruff → pytest → 与基线收据按 `failed_ids` 集合比）。门禁脚本首跑锚了自身所在树把工具树判成脏树 → 改 `rev-parse --show-toplevel`。用 `--receipt` 模式拿两张真收据验出那条新红（exit 3）。
9. 开 #551、#552、#553（#553 门禁 7574P/6F 红集=基线+墙钟条，写明由 #551 修）。
10. **① 本体**：finance-base-ab 加 `SHAPE_QUESTION_FILE`（不覆盖茅台参考题），题「2024年腾讯控股全年营业收入是多少亿元？」（港股→`financial_data` 只认 A 股→一手链为空，真值 6602.57）。参考 loop 臂：`web_search`+`kb_search` → web 真授予 5 条 `public_web` → **答 6602.57 亿元**，自标二手；Episode 臂：`news_search`+`kb_search` → kb 超时烧 23.6s → 第二轮 `would_grant 0` 但 `web_search` 无地板仍可见 → 模型点了（查询词里已写 6602 亿）→ 授 0 秒 → 弃权。两臂首轮 token 13658==13658（#542 后 ±3 门首次真过）。判官对 5 条 `public_web` 零删除、4 条 issue 全是降级标注。`web_fetch` 两臂零调用。
11. 参考 loop 臂第一次用 `&` 挂在工具 shell 里被回收没跑起来；改后台方式重跑。
12. **③**：现成 CLI `intelligence.cli tool-hunger` 扫 1218 run：12 条全是 `finance_query invalid_query`（08-27～30 盘面表参数错），`unknown_tool` / `capability_denied` 为 0，08-30 后零事件 → 不排任何新工具；⑥ 随之不排期。
13. **④ P2 第一步**：拒句账 `sentence_verdicts` 落在两个决定点（preflight 机械 / `_plan_repair_indexes` 机械·语义分流），`verify()` 外层统一挂账；读侧 `scripts/offline_judge_verdict_census.py` 对 814 历史 run 报「不可判」。6 钉、变异 2 红、判官既有 233 条零回归、pre-commit 11 道过（unread-fields 因 `to_dict` + 读侧脚本过）。#557 门禁 7576P/5F 同一组红。
14. **⑤ 采集事实**：仓里已有 `SubResearchCoordinator`（3 支 / 8 次 / 60s、子预算扣父账本、`BranchEvidenceSink` 进同一账本、同步排空不变量）；只 Episode 接了（参考 loop `can_branch=False`）；生产 814 run 里 `mode_decision` 127 条，50 条批 deep 起分支全在 08-13～08-22，**08-22 后零 deep 零分支**，PLAN 自 08-19 起只 3 个 run。写 spec `2026-09-03-subagent-tool-design.md`：包现有协调器成 dsh 形状工具，不新建；前置是查 PLAN 归零。
15. 回写：在途交接覆写（2956 字节）、本快照、10_knowledge。

## 2. 决策表（含被否方案）

| 决策 | 选了什么 | 否了什么 | 为什么 |
|---|---|---|---|
| ① 开跑前先直调搜索 | 离线调 `fetch_web_search` 五道题看内容 | 直接跑两臂 | 两臂一次 ~3 分钟 + 配额；先看最便宜的一环。结果这一环就断着 |
| web_search 判据 | `href` 含 `rdr=1` 且 `readyState=complete`；无跳转时稳定 3s | 固定 sleep；`_G.JCache`；换引擎 | 跳转时机 0.9–2.1s 不定且会话热后消失；JCache 前后都是 1；换引擎超范围且问题不在 Bing |
| 稳定窗 3.0s | 3.0 | 2.0 / 5.0 | n=4 最大跳转延迟 2.1s，留 40% 余量；无跳转时每次多 3s，20s 工具窗装得下 |
| UA 改动 | 改并保留，`CDP_USER_AGENT` 可还原 | 不改；改回 | 改后壳内容从无关页变实体页、十分钟后不再跳转，但与会话跑热分不开；改动无害、可回滚，归因写「不明」 |
| 多出的一条红 | 单独 PR 改容差 | 塞进 #553；冻结全局时钟 | 红集判据要干净；冻结 `time.monotonic` 波及其它计时逻辑；只去伪差、四个裁决键仍逐字 |
| 工具沉淀时机 | 开 PR 前先写脚本 | 交接末尾再写 | 今天要开 ≥4 张 PR、跑 ≥3 次整仓，重复就在眼前；#539 那种重复开 PR 用查重直接堵 |
| 门禁脚本对象 | 站着的那棵树（`rev-parse --show-toplevel`） | 脚本所在树 | 首跑就把工具树自己判成脏树 |
| ① 的题 | 腾讯 2024 营收（港股） | 美股 / 时事题 | 同题型同策略同授权集，只差一手链为空，把 web 之外的变量全钉住；真值可核 |
| 换题方式 | `SHAPE_QUESTION_FILE` 环境变量 | 改 `question.txt` | 茅台参考题是硬门锚，不能被覆盖 |
| P2 记账落点 | 两个决定点 + `verify()` 外层挂账 | `_drop_rejected_sentences`；改判官 JSON 契约；解析 issue 文本定出处 | 删句函数只见索引、见不到降级句；第 1 步说好不改判据；出处必须走 E 号表 |
| P2 出处口径 | 只认句内显式 E 号 | 语义匹配证据 | 「无出处被删」本身是要分开数的一类，模糊匹配会把它抹掉 |
| ③ 结论 | 不排新工具，⑥ 不排期 | 按 spec 表加 `web_fetch` 之外的形状 | 遥测零 `unknown_tool`；同时写明遥测盲区（够不着的工具它看不见） |
| ⑤ 形状 | 包现有协调器成 `sub_research` 工具；前台同步、深度 1、不做后台 | 新建子代理；抄 dsh 后台/可续接；抄「只回最终文本」 | 协调器已满足 §3.5.5 的账本要求；后台违反同步排空不变量；回文本进不了 `admit_finish` |
| ⑤ 排期 | 先查 PLAN/deep 归零，再做工具 | 直接做工具 | 工具只在 deep 可达（standard 窗 30s 装不下 60s 一支），deep 现在是零 |
| ② | 不实施「failed→藏」，改判写进交接待拍 | 照交接原样做 | 今天 2/2 的形状是 worker `ready` 但首查超时，failed→藏不会触发 |
| 合入 | 全部不合、不切 | 合入并切流以便再测 web | AGENTS.md 合入须用户确认；上午的「执行」授权不自动延伸到新的一批 |

## 3. 验证与收据

| 项 | 读数 | 收据 |
|---|---|---|
| #553 门禁 | 7574P/6F @`8864e92d`（红集 = 基线 5 + 墙钟条） | `~/.finance-runtime/test-receipts/20260903T06*-8864e92d.json` |
| #551 门禁 | 7570P/5F @`2360859b`，same_red_set | PR 评论 #3129（首版误写 7574 已改） |
| #557 门禁 | 7576P/5F @`814ee725`，same_red_set | PR 评论 #3147 |
| #552 | ruff / bash -n / 真仓 list·conflict-check / `--receipt` 揪出新红 | PR 描述 |
| web_search 前后 | 五道题壳 → 真结果 | `docs/verification/2026-09-03-web-search-bing-rdr-shell.md` |
| ① 两臂 | 参考 6602.57 一手 web；Episode 弃权；token 13658==13658 | `docs/verification/2026-09-03-web-chain-two-arm-live.md`；`finance-base-ab/out/reference-loop-0903b-web/`；run `run_20260903_142417_573363` / `run_20260903_143017_006894` |
| ③ | 1218 run / 12 事件 / 0 unknown_tool | `docs/verification/2026-09-03-tool-hunger-census.md`；`intelligence/eval/measurements/tool-hunger-2026-09-03-all.{json,md}` |
| ④ | 814 run 不可判（字段刚有） | `docs/verification/2026-09-03-judge-sentence-verdicts.md` |
| ⑤ | 127 mode_decision / 50 deep / 08-22 后零 | spec §1.3（一次性统计未入库，复现法写在 §8） |
| finance-base-ab | `8f6ea1d` SHAPE_QUESTION_FILE + 腾讯题文件 | 该仓 gitea |

**哪些结论不成立**：不能读「参考 loop 比 Episode 强」（首轮选工具的分叉 n=1）；不能读 66.8s vs 78.1s；「判官不删 public_web」只 n=1；kb_search 2/2 超时不足以说保活无效（counters 没读到）；UA 对 Bing 的贡献量级不明；3.0s 稳定窗按 n=4 定；PLAN 归零原因是 [推断]。

## 4. 后续要做的（按序）与不要做的

要做：① 用户拍合入顺序（建议 #551 → #552 → #553 → #557 → docs）并切 8792；② 查 PLAN/deep 为何 08-22 后归零（spec §7 给了抓法）；③ 切流后跑 `offline_judge_verdict_census.py` 出 P2 第 2 步；④ 挑 snippet 里没数的题复跑两臂验 `web_fetch`；⑤ 待用户拍：RAG 首查慢的处置（预热后真查一次 / 预热后 N 秒藏 / 不动）、零授予可见性（web/news/fetch 加 ~5s 地板 / `would_grant<1s` 全藏）。

不要做：不在同一棵树与他人并行改（`fwp-wt-rag-window`）；不把 `web_search` 的 3s 稳定窗当最优值调来调去（先看 `unsettled` 频次）；不在 P2 第 2 步没数之前改判据；不做子代理后台/嵌套；不把「够不着的工具」当成遥测已证明不需要；不动 90/60/30 与 deep 240/48。

## 5. 工具沉淀盘点

| 问 | 答 |
|---|---|
| 重复两次以上的手工排查 | 开 PR ×5、整仓门禁 ×3、对基线比红集 ×3——**已脚本化**（#552 `gitea_pr.py` / `run_main_gate.sh`），本篇后半段全用它们跑；切流五步仍未脚本化（本篇没切流，留给下一任，且它改生产该单独评审） |
| 只在 /tmp 跑过的脚本 | 一段 814 run 的 `mode_decision`/`branch_started` 计数没入库（spec ⑤ §8 写了复现法）；其余普查走现成 CLI 或已入库脚本（`offline_judge_verdict_census.py`） |
| 现有门禁的洞 | ① `ProviderTrace` 三态对「success 但内容错」盲——本篇修的是解析时机，没有补「相关性」门（要语义判断，成本不划算，写进 10_knowledge 当手法）；② 桩掉代理的单测看不见拼接 JS 的语法错——补了括号配平钉子；③ 逐字比较墙钟推导值——#551 |
| 可迁移的模式 | 「两步到达的页面，首批非空不是终态」「三态状态码对内容错盲」「墙钟推导值不进逐字比较」「后台任务别挂在会被回收的 shell 里」→ 写进 `10_knowledge/`（本篇末） |
| 沉淀成手法而非工具的 | 「开跑 live 前先直调最便宜的一环」——判断哪一环最便宜要看链路，做不成脚本 |
