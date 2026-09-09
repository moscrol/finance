# 方法飞轮接线（能力升级 07）：交付与验收读数

分支 `feat/cap07-method-flywheel`（基线 `gitea/main@5eb24515` + `feat/method-validation-loop` 两个提交），
任务书 `docs/superpowers/plans/2026-09-09-capability-upgrade/07-method-flywheel-goal-brief.md`，
进度 `…/progress/07.md`，范围外 `…/blocked/07.md`。本文按任务书要求分四项报告：
**已实现 / 已进默认入口 / 真实验收 / 生产生效**。

## 一句话

固定双红协议的收据现在能被三个地方读到：日报「方法信号与待验对象」段、`ask` 的 `[M]` 块、Workbench
对话的 `memory_lookup` 工具。有信号的 D0 观察会登记成 checkpoint，夜间回检到期自动按原协议结算并分类
（支持 / 方法错误 / 数据不足 / 环境变化 / 没有信号 / 非适用阶段），分类改变下一次问题里对方法的选择
（采用 / 降低 / 排除 / 候选）。**全部读数仍是 research_only**：不出胜率、不构成买卖建议。

## 已实现 [实测]

| 件 | 位置 | 判据 |
|---|---|---|
| 立场派生与摘要缓存 | `intelligence/services/method_validation/flywheel.py`（`derive_standing / refresh_standing / load_standing / decide`） | 摘要按输入指纹命名，收据一变即报过期；106MB 原件只在 `status --refresh` 时读一次（6.2s） |
| 回检六类分类 + 环境标记 | `flywheel.classify_day / classify_forward`；`study.read_market_stages` | 单测覆盖八种日期形状；小 DuckDB 端到端两臂（主升→支持、下跌→环境变化） |
| 观察 ↔ checkpoint | `flywheel.register_observation_checkpoint / record_observation_verdict`；`checkpoints.OBJECT_TYPES += method_observation`；`METRIC_TYPES += method_validation` | 无信号 / 非适用阶段不登记；环境变化 / 数据不足 → unverifiable 不进分母（`calibrate().scored == 0`） |
| 夜间自动回检 | `checkpoint_resolvers.MethodValidationResolver`（按 `metric.type` 路由） | 到期前只降级并写清要跑什么；到期后与 CLI 同结论 |
| 记忆召回 | `user_memory.MemoryRecall.methods`；`episode_tools.memory_lookup_runner` 多一类「方法验证读数」证据 | 问题含「双红」才召回；别的用户目录为空；`光刻胶` 类问题召回数不变 |
| 日常入口 | `workflows/daily_agent.py` 报表 `method_flywheel` + markdown 段；`api/daily_reports.project_daily_agent` section | 无实验时一行说明，不让日报失败 |
| CLI | `scripts/method_validation.py`：`capture` 登记、`recheck` 分类回写、`status`、`match`、`candidate`、`daily` | `daily` 只在条件成立时动作；主库路径不存在 fail closed |

测试：`intelligence/tests/test_method_flywheel.py` 12 项；连同既有相关回归 **242 passed**（收据
`~/.finance-runtime/test-receipts/20260909T064832Z-b3741d80.json`），`ruff check .` 通过，`layer_audit.py`
ERROR 0。全仓 pytest 读数见 progress/07.md 执行记录。

## 真实数据读数 [实测]

- 第一轮离线根（R-20260908-05）`status --refresh --today 2026-09-09`：历史演练 77 / 18 / 2；信号日分类
  **数据不足 16 天、方法错误 2 天**；选择 **降低权重（仅作观察提示）**；真实前向「起点 2026-09-10，尚无真实观察」。
- 16 个「数据不足」日的根因：固定 8 个 `.TI` 板块双红标签整段 NULL（见 progress/07.md 样本表）→ 归 08。
- 验收用户目录 `~/.finance-runtime/cap07-users/linxiaoqi5111`（`FORESIGHT_USERS_DIR`，不碰生产用户目录）：
  `register` + `history` 重跑 40s，`comparison` / `features` 内容摘要与第一轮原件**完全一致**（确定性）。
- `scripts/probe_tool.py memory_lookup --query "连续三日双红的板块，后五天历史上表现怎么样？我们验证过的方法怎么说"`
  （同一用户目录）：status=success，evidence=1，0.08s，证据标题「方法验证读数」，正文含历史演练 / 真实前向 /
  降低权重 / 不构成买卖建议。
- `daily --no-rebuild`（09-09 白天）：见 progress/07.md（capture 因「前向起点 09-10 未到」跳过、无待验对象、
  摘要刷新）。

## 已进默认入口 / 真实验收 / 生产生效

- **已进默认入口**：`memory_lookup` 工具是 Workbench 对话默认工具面的一员（验收实例 run 的授权列表含它，
  14 个工具）；`[M]` 块与日报段随既有入口生效，不需要开关。
- **真实验收（Workbench 对话）**：见下节，按实际发生填写。
- **生产生效**：**未做**（任务书：不切生产）。生产 8792 仍是旧 revision；生产用户目录下没有 `method_validation`
  实验——上线后需在生产用户目录 `register` + `history` 一次（40s），并把 `daily` 接进夜跑（沿原任务授权）。

## 真实对话验收记录

验收实例：`~/.finance-runtime/cap07-acceptance/start-cap07-workbench.sh`（环境形状抄生产启动器，改代码根 /
用户目录 / 端口 8807），驱动脚本 `drive.py`（走 `POST /api/conversations/{id}/messages`）。

- 14:57 第一次：`run_20260909_145743_955868`，question_type=`comparison_analog`，tier=max，engine=episode，
  授权含 `memory_lookup`。**模型两轮全部 HTTP 429**（`model_turn.error="LLM 调用 HTTP 429"`，provider_attempts=2），
  终局恢复也 429，答案为模板性弃权。随即用 Keychain key 直探网关：`gpt-5.6-sol` / `gpt-5.6-terra` 均
  `model_cooldown`，`reset_seconds≈3803`（约 16:01 解除）。生产 8792 同网关同状态。**这一轮不算验收**。
- 已排 16:08 一次性提醒续跑两题（相似不相同）：
  1. 「连续三日双红的板块，后五天历史上表现怎么样？我们验证过的方法怎么说」
  2. 「双红持续了四天以上的板块，现在还值得追吗？上次那个方法的结论还成立吗」
  判据：`continuous-episode.json` 里 `memory_lookup` 被调用且证据含「方法验证读数」；回答区分历史演练与真实前向、
  说明为何降低权重 / 不据此排序；第二题能引用同一读数解释「结论仍是历史演练结论」。

（续跑结果追加在此。）

## 未验证 / 已知边界

- 真实前向观察尚未发生：协议起点 09-10；capture 依赖当日 daily-full 落库后 `build-labels`。第一个真实对象
  最早 09-10 收盘后登记、09-17 前后结算；在此之前**不能**声称「真实飞轮已转一圈」。
- 夜间 03:50 回检能自动结算的前提是旁路库已重建；没有日程做这件事（blocked/07.md #3），未重建时 resolver
  只会 unverifiable 并写清要跑 `daily`。
- 选择梯子是确定性规则不是统计门；OPT-04/05 的相关样本、留出与多重检验仍在基础补强任务。
- 问题命中只认「双红」关键词；别的固定方法要加自己的匹配词与协议。
- 主库 09-08 复盘未落库（readiness `market_data_consistency=false`，生产同状态）。
