# 在途交接 · 能力放大 / 工具线（spec/capability-amplification-output-gate）

## 这个分支做什么
按 knevo 的工具设计理念补工具面、契约自己做。spec `docs/superpowers/specs/2026-09-02-capability-amplification-output-gate-design.md`；展开 `docs/handoffs/2026-09-03-capability-line-session-handoff.md`（上午）与 `2026-09-03b-capability-line-web-chain-and-p2.md`（下午）。

## 决策与被否方案（下午新增）
- web_search 只认 Bing `rdr=1` 跳转页 + 3s 稳定兜底 / 否固定 sleep、否 JCache 判据、否换引擎 / 壳→跳转时机不定且会消失
- 墙钟推导值按容差比 / 否冻结全局时钟 / 只去伪差，四个裁决键仍逐字
- P2 记账落决定点不落删句函数 / 否改判官 JSON 契约 / 删句函数看不见被降级的句子
- 子代理 = 包现有协调器成工具 / 否新建、否后台可续接 / 同步排空是承重不变量
- ③ 遥测零信号 → ⑥ 不排期
- （0903f）三项待拍已拍：RAG 走「先判别再修」、零授予走「MIN_WINDOW_SECONDS 加三行 ~5s」、deep 走「治理侧不经 PLAN 按 observable 升档，排在 RAG 之后」

## 当前状态
用户「你来合并」→ #551/#552/#553/#557/#560 全合，8792 已切 `f4c03b9ae610`（0903e，回滚锚 `~/.finance-runtime/cutover-20260903e-rollback-8792.txt`）。仓外：`~/scripts-local/chrome_debug_agent.sh` 加了 `--user-agent`（去 Headless），`CDP_USER_AGENT` 置空还原。

**0903f（本轮，三张 PR 全 open 未合、8792 未切）**：#566 RAG 超时处置 / #567 工具窗地板 / #568 deep 升档。树 `/Users/a77/fwp-wt-rag-abandon`，三支均自 `gitea/main@aa3d87e4`，`conflict-check` 三条 clean。批次门禁在合成树 `integration/tool-window-and-deep-0903@61d4a0db`（本地临时分支，未推）：**7604P/5F**，红集与基线同一组（5 条 `test_dream_mine` 环境项），ruff 绿，webapp 四件套绿（本批零 webapp 改动）。

⚠ **8792 已落后 main 两档运行时改动**：`f4c03b9a..aa3d87e4` 含 #562（画像整表回写棘轮）、#555（复盘台账 JSON），另有 #558（chore）。0903f 切流窗口开着但无人认领 —— 那两张不是本线合的。

`fwp-wt-rag-window` 那份未提交的 `rag_worker.py` 与 main 上已有的保活实现内容等价（该树停在 `94f5daae`，落后 main），不是在途新工作，勿据此以为有人在改 RAG。

## 未验证 / 已知边界
- `web_fetch` 两臂零调用（snippet 里就有数），仍无 live 读数；#567 给它的 5s 地板是 [推断]，无实测样本。
- 判官对 public_web「零删除」只 n=1；P2 占比要等积累。
- **KB 命中全被 `require_fresh` 丢掉**：#566 修完 `kb_search` 不再超时，但 24 条命中全丢、`hits=0` / `ok=False`。~~需重建索引，另立单~~ **已更正：重建索引救不回来**——①`index_freshness` 是**整库**结论（manifest 一个指纹），实测 14412 个入索引文件只有 37 个受影响（0.26%），99.74% 逐字节没变的页被连坐；②常驻 worker 在预热时把整库 verdict 算一次就冻住，重建后不重启 worker 不生效。已修：KB 仓 `fix/rag-page-level-freshness`（按页判，整库两道门保留）+ 本仓 `fix/rag-worker-page-freshness`（每次请求现算）。真索引实测：修前 12 条全 stale、修后 11 fresh / 1 stale（那 1 条是真改过的页）。索引 `built_at` 是 08-31 **19:01**，19:27 是目录 mtime，此处原写 19:27 口径混了。
- #567 只止损，不会让 `web_search` 拿到真授予；要 #566 一起上，窗才留得住。
- #568 让 deep 在 GLM 下可达之后，生产 deep 占比会变 —— 合入后要看第一批 `observable_complexity_without_plan` 的读数，别默认它一定是好事。

## 已撤回的推断（详见 `docs/verification/2026-09-03-kb-search-timeout-root-cause.md`）
- ~~「kb_search 刚预热仍首查超时，选 a 预热后真查一次 / b 预热后 N 秒藏」~~ —— **整个选项集打偏**。`prewarm` 本来就发真查询；修复后第一次生产形状查询 11.93s、第二次 13.58s，30s 窗够用、`--k 1` 预热形状也够用。真因是 except 子句顺序把两个超时处置器变成了死代码。
- ~~「保活 counters 在臂进程内没读到 → 臂和预热不是同一进程」~~ —— 证伪。`run-reference-loop.sh` 起的臂就是自己的进程、自己预热。probe_tool 全 30s 是因为**它不预热**，冷 worker 加载 50–145s > 30s 窗。
- `scripts/probe_tool.py` docstring 引的 `research_owner.py:65`（「预热后首查仍要约 28s」）**该文件在 main 上已不存在**，出处查不到，未采信。

## 下一步
1. 用户拍 #566/#567/#568 合入顺序（建议 #566 → #567 → #568，deep 必须在 RAG 之后）与 0903f 切流。
2. 切流后复量：`kb_search` 超时率是否从 66% 掉下来、`web_search` 能否拿到第一次真授予、`observable_complexity_without_plan` 的第一批读数。
3. 生产积累后跑 `scripts/offline_judge_verdict_census.py --since 2026-09-03` 出 P2 第 2 步占比（首读 1 run/1 条，只证链路通）。
4. 换题复跑两臂验 `web_fetch`（挑 snippet 无数的题）。
5. KB 索引重建单（本线不做）。

## 踩过的坑
- `status=success` 内容全错：三态看不出，直调一次看结果再跑 live。
- 拼接 JS 少/多一个括号 → 代理 4xx，桩测试看不见，配平钉子。
- 门禁脚本锚自身所在树会判错树，用 `rev-parse --show-toplevel`。
- 后台命令别用 `&` 挂在工具 shell 里，会被回收。
- **专用异常处置器排在宽子句之后 = 死代码**，症状会伪装成「下游那条路太慢」。写「先试快的、失败降级到慢的」时，降级分支捕的异常集合必须与上游**实际会抛**的类型逐个对过——尤其上游新增了继承自内建异常的自定义类。
- **诊断先读运行时 counters 再上探针**：`/api/readiness` 的 `queries_served=1 / abandoned=1` 一条就把「worker 从没成功服务过」钉死了，比跑探针快也准。
- 行为钉里的阈值要**从生产那张表取**，不写字面量——写死的话生产表漏了那条它照样绿，钉住的只剩机制不是取值。

## 已验证
0903e 切流 main tip 7581P/5F 同一组红、三项验证过；腾讯题两臂 live：参考臂 6602.57 亿元 web 证据绑定发布。
0903f 合成树 `61d4a0db` 7604P/5F 同一组红、ruff 绿、webapp 四件套绿；三条修改各自变异证伪过（#566 还原子句顺序→两钉红、阳性对照绿；#567 抽掉地板→申报表钉+行为钉双红；#568 门槛设 99 / 去掉两个前置→各自红）。
