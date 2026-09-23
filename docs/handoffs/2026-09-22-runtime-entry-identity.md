# 恢复前先问「这是谁的 episode」——入口身份绑定

日期：2026-09-22 ｜ 分支：`fix/runtime-entry-identity-0922`（基线 `e7e12a189`，即 PR #843 的最新提交）

## 背景（不读这段会误判后面每个决定）

运行底座已经有两道门：

- **授权快照（authorization snapshot）**：检查点里存着当时的完整任务合同、策略、信息截止与工具声明。恢复时由调用方**重新提供** `context` / `registry`，逐字节比对，不一致就拒。它回答的是「这一轮**能做什么**」。
- **单写者（single writer）**：`episode_store.writer` 用本机 POSIX `flock`（文件锁）保证同一时刻只有一个进程在写这个 episode。它回答的是「**现在谁能写**」。

两道门都不回答第三个问题：**这一轮是谁的**。检查点里的每一个字段，都是那个崩掉的进程自己写的；拿它自己来证明自己的归属，等于让待校验的数据替自己签字（自授权，self-authorization）。此前交接文档里反复出现的「仍须入口用户身份绑定才可驱动续跑」，缺的就是这一块。

具体的坏形状：多用户 Workbench 下，用户 B 的一次请求只要拿到（或猜到）一个 episode 编号，就能让恢复逻辑把用户 A 的现场读出来、把 A 的计划接着跑下去——合同一样、工具一样，前两道门都不会响。

## 按发现顺序做了什么

1. **先找身份在哪儿汇聚**：`intelligence/api/app.py::_build_continuous_turn_adapter` 手里同时握着 `run_id`、`assistant_message_id`、`conversation_id` 和 `RunStore`（它带 `user_id`）。生产的 episode 编号就是 `f"{run_id}:{assistant_message_id}"`。再往下（`ContinuousTurnAdapter` → `ContinuousAgentEpisode`）身份就断了：`EpisodeScope(user_id="")` 那行注释写得很清楚——运行器拿不到，也不该拿。
2. **确认断点不是疏忽而是设计**：`memory_lookup` 的用户身份是**装配期**绑进 `registry_factory` 的，刻意不穿过 adapter 的参数表（否则会打断一批固定参数的测试替身）。所以新身份也不能靠给 `registry_factory` 加参数来传。
3. **确认检查点侧缺字段**：`EpisodeState` 有 `budget_snapshot` / `authorization_snapshot` / `evidence_snapshot`，没有任何「主人」字段。
4. **实现**：新增 `intelligence/services/episode_entry_identity.py`（两个 frozen dataclass + 捕获/校验函数）→ `ResearchRunContext` 加尾部默认字段 `entry_identity` → `_EpisodeLedger.put_state` 与另外三份快照同一套围栏（fence）捕获 → `restore_episode` 在授权门之后加身份门 → adapter 在铸出 task_id 之后盖章 → app 装配期核验 run 归属后签发。
5. **补反例测试** `intelligence/tests/test_episode_entry_identity.py`（35 例）。
6. **复查恢复自己写回去的检查点**：发现 `close()` 与 `resumable()` 重建 `EpisodeState` 时逐字段列举，会把新字段丢掉——那等于「恢复一次就把主人忘了」，下一次任何未绑定调用方都能接管。补上并加了专门的回归用例。

## 决策与被否方案

### D1 身份从哪来

| 方案 | 评价 | 结果 |
|---|---|---|
| 从旧日志/检查点里读出用户名，作为身份 | 待校验的数据替自己授权；崩溃前被篡改或本来就写错，恢复无从发现 | **否** |
| 请求参数（`?user=`）直接信 | 客户端自报，跨用户接管只差一个参数 | **否** |
| 入口拿服务端已存的 `run` 记录核验（`run.user == run_store.user_id`、`run.session_id == conversation_id`），核过再签发 | 用的是另一份独立持久化的事实，不是本次请求的自述 | **选** |

代价：没有 `RunStore` 的装配（离线驱动、CLI、多数测试）签不出身份，只能保持「未绑定」。这是如实陈述，不是降级。

### D2 未绑定（`None`）怎么处理

| 方案 | 评价 | 结果 |
|---|---|---|
| 未绑定视为通配：谁都能恢复 | 等于给旧检查点开后门，且「恢复一次丢字段」就能把任何 episode 降级成公共资源 | **否** |
| 一律要求绑定，未绑定的旧检查点不可恢复 | 语义最干净，但会一次性推翻仓内上百个恢复用例的调用形状，且离线复盘工具也被一并关掉 | **否（本轮）** |
| 对称比对：两边都未绑定才算一致；一边有一边无就是不匹配 | 生产链路永远有身份，所以生产检查点永远被绑定保护；离线/测试链路保持可用且被标记 `entry_identity_bound=False` | **选** |

`RestoreResult.entry_identity_bound` 这一位是留给将来自动续跑驱动的：驱动应当要求 `True`，而不是自己去猜主人。

### D3 身份绑在哪一层

| 方案 | 评价 | 结果 |
|---|---|---|
| 塞进 `ResearchTaskContract`（任务合同） | 合同进授权快照、也进模型可见的配置摘要；身份会顺着漂到提示词与收据里 | **否** |
| 给 `registry_factory` / `context_factory` 加参数 | 会打断一批固定参数的注入式测试替身（既有先例明确否掉过） | **否** |
| 放 `ResearchRunContext` 的尾部默认字段，由 adapter 在 `_run_episode` 里**无条件覆写** | 位置构造向后兼容；且「只有入口能盖章」——context 工厂（含注入替身）自己填的一律被覆盖 | **选** |

### D4 什么时候绑定 episode 编号

| 方案 | 评价 | 结果 |
|---|---|---|
| 装配期就绑好 `episode_id` 传给 adapter | `task_id_factory` 是可注入的；预绑会把旧编号盖在新 episode 上 | **否** |
| 传未绑定的 `EntryIdentity`，在 `_run_episode` 铸出 `task_id` 之后 `.bind(task_id)` | 一份身份不可能被搬到另一个 episode 上 | **选** |

### D5 中途换主人怎么办

选：`put_state` 发现新捕获的身份与上一份检查点不一致（含「变成未绑定」），直接按**保存失败**处理（与预算/授权/证据快照同一套围栏：`persistence=failed`、`stop_reason=storage_failed`，停止新效果、保留草稿）。否了「以新为准」和「静默保留旧值」——前者允许运行中被改主人，后者让检查点与现场不一致却装作正常。

## 验证与收据

本机 `.venv-workbench` 解释器，工作树 `/Users/a77/fwp-wt-runtime-entry-identity-0922`：

- 新套件 `intelligence/tests/test_episode_entry_identity.py`：35 passed。
- `intelligence/tests/conformance` + restore/store/writer/persistence/authorization：317 passed, 3 skipped, 1 xfailed。
- `test_continuous_turn_adapter` / `test_agent_episode` / `test_episode_session` / `test_episode_steer` / `test_episode_inbox`：261 passed。
- `test_workbench_api.py`：126 passed。
- `-k "episode or research_contract or run_store or restore or contract"`：2040 passed。
- Ruff：改动文件全绿。
- 全量 `pytest -q -p no:randomly`：13044 passed, 87 skipped, 2 xfailed, **1 failed**，2301 秒。
  唯一的红是 `test_workbench_conversation_integration.py::test_skill_timeout_degrades_one_module_and_continues`：
  该用例的 `_SlowSkill` 睡 1.2 秒对 `timeout_seconds=1`，只有 0.2 秒余量；它直接构造 `TurnOrchestrator`，
  不经过 `_build_continuous_turn_adapter`，也不碰 episode 存储/恢复。单跑（107 秒）与整文件跑（111 秒）均绿。
  **没有**在同等负载下跑基线对照，所以只能断言「与本改动无路径交集、且对负载敏感」，不能断言它在 main 上同样会红。

不成立的结论：这些测试证明的是「跨用户/跨会话/跨 run/未绑定的组合会被拒、且拒绝时不写盘」，**不**证明续跑安全——续跑驱动还没写，未知效果与费用对账也还没做。

## 后续要做的

1. 未知效果 / 费用对账（同一条主线里最硬的一块）：崩溃前那次外部请求是否已执行、是否已计费，锁和身份都答不了。
2. 跨进程恢复驱动：在临时目录做真实进程中断验收，要求 `entry_identity_bound=True` 才允许自动续跑。
3. 关联子 episode（父子任务）的恢复仍在 `restore_episode` 里整体拒绝，不在本轮范围。

## 不要做的

- **不要**因为「身份对上了」就放宽授权快照比对：D 中的伪造检查点用例专门钉住了两道门各管各的。
- **不要**为了让旧检查点能恢复而把 `None` 放成通配（D2 否掉的第一个方案）。
- **不要**把身份写进合同 / 配置快照 / 事件流：`test_owner_identity_never_reaches_the_model_or_the_event_stream` 会红。
- **不要**在恢复重建 `EpisodeState` 时新增字段却不透传：这类「逐字段列举」的构造点目前有两处（`close()` / `resumable()`）。
