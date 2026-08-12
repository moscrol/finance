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

1. **R3 已出**（run=20260812T155420Z）：真值 0/7、fact 层 12（=R1，**#293 无效果**）；运行面明显变好（8/10 完成、A3 首次跑通、product_language 2→0 但该层噪声大不作数）。
2. **#293 的深归因**：翻 R3 A1 的 draft——数字是「模型没写」还是「写了被绑定规则删」？两者修法完全不同（前者=描述没到位/被忽略，后者=要配套放行已绑定数字的表述）。
3. **LLM 超时 harness 策略**（A7 本轮仍中招 31s failed）：对口判据 `serial-phase-budget`。
4. knevo 后续：suggest_options 缺口镜像、report→track 接力。
5. TOOLKIT 待补：变异还原禁用 `git checkout <file>`，成文已交用户。

## 踩过的坑

- **归因先翻 episode 产物再下结论**：R2 退化我先猜「#293 触发删句级联」，产物证伪——A1 根本没写出草稿（deadline_exhausted 31s 零产出）。中途读数会骗人。
- 中转晚间超时会整轮污染对照；挑稳定时段跑。
- 隧道 530=Mac 侧 cloudflared 掉线，云端只能等；长命令 nohup+轮询（CF 100s 上限）。

## 已验证

- R2 归因链完整：continuous-episode.json 的 outcome/semantic_verifier/model_error 三层。
- #294 修的两缺陷均来自 R2 真实产物（gap 标签指令泄漏、25 条证据零绑定无感知）。
