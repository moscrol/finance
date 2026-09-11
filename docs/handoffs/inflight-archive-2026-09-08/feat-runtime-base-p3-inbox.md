# feat/runtime-base-p3-inbox

## 这个分支做什么
运行底座 P3（工单 #30）：收件箱 `Inbox`——外部输入唯一通道，入箱 / 认领 / 丢弃三事实 durable（INV-R5）。叠在 P2 #638 上，基线 `673cc8da`。

## 决策与被否方案
- 正文只在 `inbox_inserted` 落一份，`inbox_claimed` 只带 id，派生按 id 回找。否：两处带正文——投影剔两处、多一份可漂副本。
- 领域判定在 `send` 时做（发送方当场拿回执），抛异常按拒收。否：认领时判——端点拿不到同步答复。
- 清箱挂 `_EpisodeLedger.add("finish")`（与 `done` 同出口），`resume()` 重开。否：十个 return 点各清——必漏。
- `keep_inbox` 落为 `Inbox.keep_on_cancel`，不进 `CancelSignal`。否：取消信号带收件箱语义——两概念耦死。
- 停机点认领 `next_turn` + 此刻已到的 `next_step`；收口阶段不认领。否：收口也认领——再开一轮烧穿合成窗。
- 子研究回灌也过 `admit_inbox_message`（harness 看 `source`）。否：内部来源绕过——「唯一通道」多出第二条门。
- 发射点写字面量 kind（目录 AST 扫描只认字符串常量）；统计计数器删了（`unread-fields` 门禁拦下）。

## 当前状态
已提交 `c044cf2b`（13 文件；新 `services/episode_inbox.py`、`tests/test_episode_inbox.py`、`conformance/test_inv_r5_inbox.py`）。PR 见项目笔记索引行；全量读数见 PR 正文。**合入顺序 #620 → #624 → #638 → 本单**。

## 已验证
- 单元 8 + conformance 14 绿；变异（停机点不认领 / finish 不清箱 / 请求前不认领）各红 2 / 4 / 2。
- 既有 runtime 套件 428 绿，严格派生全程开着；`gen_runtime_catalog --check` 一致（durable 34 种、接缝 17 方法）；ruff 0；pre-commit 11 道过。

## 未验证 / 已知边界
- Workbench `steer` 端点与 CLI 未做（§12 第 4 题）；唯一外部入口 `GLMAgentRuntime.steer`。
- `wakeup` 只记账（同步 loop 无空闲态，等 P4 `step()`）。
- `restore` 不处理箱里未决 `inserted`（合成 finish 不补 discarded）——P4「restore vs 在飞驱动」一起收。
- 子研究回灌从「批后立刻」挪到「下次请求前」，可能排在收口指令之后，未 live 对照。
- 参考 loop 未接收件箱（声明表 R5 只给 continuous）。

## 下一步
- 按序合入；P2 起改生产行为，切 8792 走五步规程，切后 `steer` 探针一次。
- P4（#31）：竞态目录 ≥ 8 × 2 序（本单已给「steer vs 停下」两序形状）、oracle 升公共件、`step()`、`defensive-patterns.md`。

## 踩过的坑
- `completed_finish()` 夹具绑证据哈希，没先跑 market 工具的终局被 `forged_hash` 拒成 partial——follow-up 场景先来一轮取证。
- `event_sink` 在 `model_turn` 落账时递话 = 「模型已停、loop 未判」的 B 序注入点，不用给 loop 加钩子。
