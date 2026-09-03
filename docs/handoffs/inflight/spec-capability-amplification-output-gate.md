# 在途交接 · 能力放大 / 工具线（spec/capability-amplification-output-gate）

## 这个分支做什么
按 knevo 的工具设计理念补工具面、契约自己做。spec `docs/superpowers/specs/2026-09-02-capability-amplification-output-gate-design.md`；展开 `docs/handoffs/2026-09-03-capability-line-session-handoff.md`（上午）与 `2026-09-03b-capability-line-web-chain-and-p2.md`（下午）。

## 决策与被否方案（下午新增）
- web_search 只认 Bing `rdr=1` 跳转页 + 3s 稳定兜底 / 否固定 sleep、否 JCache 判据、否换引擎 / 壳→跳转时机不定且会消失
- 墙钟推导值按容差比 / 否冻结全局时钟 / 只去伪差，四个裁决键仍逐字
- P2 记账落决定点不落删句函数 / 否改判官 JSON 契约 / 删句函数看不见被降级的句子
- 子代理 = 包现有协调器成工具 / 否新建、否后台可续接 / 同步排空是承重不变量
- ③ 遥测零信号 → ⑥ 不排期

## 当前状态
main=`c19f7594`；8792=`c88c81da5120`（未切，不含下面任何一张）。**待合入（需用户确认）**：#553 web_search 修复 · #551 墙钟用例 · #552 门禁/PR 脚本 · #557 P2 拒句账 · 本线 docs PR。五张对 main 冲突探测全净。`fwp-wt-rag-window` 仍有他人未提交 `rag_worker.py`，勿拆。仓外：`~/scripts-local/chrome_debug_agent.sh` 加了 `--user-agent`（去 Headless），`CDP_USER_AGENT` 置空还原。

## 未验证 / 已知边界
- `web_fetch` 两臂零调用（snippet 里就有数），仍无 live 读数。
- kb_search 刚预热仍首查超时 2/2；保活 counters 在臂进程内没读到。
- 判官对 public_web「零删除」只 n=1；P2 占比要等 #557 合入切流后积累。
- PLAN/deep 归零原因未查（[推断] 08-22 prompt 重构）。

## 下一步
1. 用户拍合入顺序并切 8792（含 #553 才能再测 web）。
2. 查 PLAN/deep 为何 08-22 后归零——子代理 spec 的前置（spec §7）。
3. 切流后跑 `scripts/offline_judge_verdict_census.py` 出 P2 第 2 步占比。
4. 换题复跑两臂验 `web_fetch`（挑 snippet 无数的题）。
待用户拍：② 改判——RAG「worker ready 但首查慢」不是 failed→藏能管的，选 a 预热后真查一次 / b 预热后 N 秒藏 / c 不动；零授予——web/news/fetch 无地板在 `would_grant=0` 仍可见（live 实锤），加 ~5s 地板还是 <1s 全藏。

## 踩过的坑
- `status=success` 内容全错：三态看不出，直调一次看结果再跑 live。
- 拼接 JS 少/多一个括号 → 代理 4xx，桩测试看不见，配平钉子。
- 门禁脚本锚自身所在树会判错树，用 `rev-parse --show-toplevel`。
- 后台命令别用 `&` 挂在工具 shell 里，会被回收。

## 已验证
#553 7574P/6F（+1 墙钟红，#551 修）、#551 7570P/5F、#557 7576P/5F，红集均 = 基线 5 条 dream_mine；腾讯题两臂 live：参考臂 6602.57 亿元一手 web 证据绑定发布。
