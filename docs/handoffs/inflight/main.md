# 在途交接 · main

更新：2026-08-12 · Cursor Cloud（经 exec 隧道操作本机，工具 scripts/rexec.py）

## 这个分支做什么

修「自建 agent 效果差」：#287–294 八个 PR 全合并，生产已部署 `ad743a64`。数据链全绿（daily-full 三道门 + 快照对账 PASS + 覆盖审计）。

## 当前状态

- **A 组验收第三轮跑到一半**（日志 /tmp/acceptance-a3-20260812.log，run JSON 落 intelligence/eval/runs/）。前 7 题：6 题带证据完成（A3 个股深挖首次跑通），A7 failed 31s（疑 deadline 族）。
- 三轮对照口径：R1=5b7464be（修复前基线）、R2=11da9707（被 LLM 超时污染，4/10 题 deadline_exhausted/repair_model_unavailable，产物实证 TimeoutError）、R3=ad743a64。**R2 不可用于 #293 判决**。
- #292 已生产验证（A5 渲染出验证窗口段）；#293（盘面槽位要数值）效果待 R3 board 判：fact 层 R1=12 条，看走向。
- knevo 结论：BaseFinanceMode/closed_loop_retrieval 只在引擎 B、被 cutover 孤儿化；#292/#293/#294 是接线第一批。

## 下一步

1. **#295 待合并（量具修复，重大）**：`_NUMBER_RE` 的 `(?<![\w])` 在中文紧邻时把数字整窗撕碎（21949.97→97）。修复后零配额重判：R3 真值 **0/7→1/7（A1 全绿，史上第一个 PASS）**、fact 12→6；R1 重判不变（当时真缺）。**此前「#293 无效果」结论作废——数值注入实际生效**，被量具 bug 掩盖。
2. 剩余 6 条 fact 红已归因：A3/A4 真缺数字；**A5 日期错位**（07-23 的题拿 08-12 证据作答成「电力最集中」，真值储能 40——且被路由进 general_finance_qa 泛型桶，双重问题，待立案）；A9/A10 超时降级。
3. **LLM 超时 harness 策略**（A7 R3 仍中招，设计已定待实现）：
   ① repair 路径 `agent_episode.py:1139` 对 turn.error 一击终局——超时类错误应在
   repair deadline 余量足够时**单次重试**（马书 ch1「超时重试=Harness 纠正层职责」
   + ch2「重试配熔断」，上限 1 次）；主路径 :639 已有 finalization 恢复层不用动。
   ② R2 A1 deadline_exhausted 于 31s ≈ quick 档 30s 预算——**同题两轮 tier 不同**
   （R1 跑了 103s），查 tier 分配的方差来源（research_contract.py:390 for_tier）。
4. knevo 后续：suggest_options 缺口镜像、report→track 接力。
5. TOOLKIT 待补：变异还原禁用 `git checkout <file>`，成文已交用户。

## 踩过的坑

- **归因先翻 episode 产物再下结论**：R2 退化我先猜「#293 触发删句级联」，产物证伪——A1 根本没写出草稿（deadline_exhausted 31s 零产出）。中途读数会骗人。
- 中转晚间超时会整轮污染对照；挑稳定时段跑。
- 隧道 530=Mac 侧 cloudflared 掉线，云端只能等；长命令 nohup+轮询（CF 100s 上限）。

## 已验证

- R2 归因链完整：continuous-episode.json 的 outcome/semantic_verifier/model_error 三层。
- #294 修的两缺陷均来自 R2 真实产物（gap 标签指令泄漏、25 条证据零绑定无感知）。
