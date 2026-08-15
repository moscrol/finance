# S3 · 超时窗口比例化：常量改为按 reserve 推导

- 索引：`2026-08-15-bookgap-index.md` · 靶：08-10 审计自认的「正解」 · 仓：finance · 优先级 P1
- **串行依赖：R-24 落地后再动 verifier；与 S2 函数不相交可紧邻，见索引 §2**

## 1. 背景（证据）

- 08-10 实测：工具批次与 judge 窗口各有**与 tier 无关的字面量硬上限**，
  deep 档多给的时间「根本流不到这两个组件」；单独抬 judge 窗口会把
  草稿饿死（两者共用 synthesis reserve）——**这两个常量不能各自独立调，
  要连同 reserve 一起算**。
- 现状（2026-08-15）：靠 env 打补丁——启动器 `ASK_TOOL_BATCH_TIMEOUT=60`、
  `MAX_SEMANTIC_JUDGE_WINDOW_SECONDS=60.0`，且启动器注释明写
  「standard 档把 judge 窗口提到 60 会重演草稿饿死，刻意没提」。
  即：**deep 档验证过的值被全局 env 顶着，standard 档的安全性从没算过**。
- 08-10 审计原话：全局改默认需要「把窗口改成按 reserve 比例推导而不是
  固定常量——后者才是正解，但属于设计变更」。本 spec 就是那个设计变更。

## 2. 目标 / 非目标

- 目标：工具批次上限与 judge 窗口从固定常量改为
  `f(tier.total_seconds, synthesis_reserve, remaining)` 的推导值，
  env 变量降级为**天花板**（取 min），不再是唯一来源。
- 目标：每档（quick/standard/deep）给出推导表并用测试钉死，防止
  「同一改动在错的档位得出相反结论」重演（08-10 最贵的一课）。
- 非目标：不改各档 `total_seconds` 与 reserve 本身；不动 fixture 的
  tier 声明；不碰 `_marker_loss_partial_public`。

## 3. 改动面

| 文件 | 改什么 |
|---|---|
| `intelligence/services/research_contract.py` | 推导函数落点（`stage_timeout` 语义扩展或新 `derive_stage_caps(policy)`） |
| `intelligence/services/episode_tool_batch.py` | 字面量 `stage_timeout(30.0)` 改读推导值 |
| `intelligence/services/episode_semantic_verifier.py` | 窗口函数改读推导值（**只动窗口推导函数**） |
| 测试 | 三档推导表快照测试；「standard 档 judge 窗口不得挤占草稿」的不变量测试（draft 可用时长 ≥ 实测需要的 26–91s 下界） |

推导原则（写进代码注释）：工具批次 cap ≈ `min(env 天花板, remaining − reserve)`
本来就有，缺的是**字面量下限**换成按 reserve 余量分配；judge 窗口 ≈
reserve 的固定比例（deep 75s reserve 下推出 ≥25s——08-10 臂 C 实测 judge
需要 13.3–24.1s，25s 窗口 6/6 成功），standard 60s reserve 下推出的值必须
保住草稿下界，宁可 judge 降级也不饿死草稿。

## 4. 验收判据（预注册）

1. deep 档推导值复现臂 C 形态：夹具跑 judge 窗口 ≥25s、工具 cap ≥60s。
2. standard 档：推导出的 judge 窗口 + 草稿时长在 90s 总额内自洽
   （不变量测试红线：草稿 <26s 即失败）。
3. env 仍可下压（运维保险丝），但去掉 env 后系统落到推导值而不是 30.0
   字面量（测试断言）。
4. 全量相关单测绿；离线 3 题冒烟（deep 1 + standard 2）结构判定不劣于
   现状臂。

## 5. 风险

- standard 档可能推导出「judge 装不下」的结论——那就让它显式降级
  （跳过语义 judge 记 `judge_skipped_budget`），这比静默超时 0/6 诚实。
  该行为要进收据字段，验收台能读。
