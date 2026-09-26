# 在途交接 · feat/river-context-projection（工单 #34 / G-14）

## 这个分支做什么
在河切片与任何消费方之间插一层纯函数 `river_projection.project()`：选了什么、按什么规则选、省了什么、限制与缺口，全部显式并哈希成 `projection_hash`；`guided_reading` 改为它的消费方；`checkpoints.register_checkpoint` 对 agent 产物（`agent_judgment` / `observation_script`）无哈希拒收。契约照 09-06 spec §4.5（在 PR #666 分支里），收据 `docs/verification/2026-09-08-river-context-projection.md`。

## 决策与被否方案
- 哈希覆盖 `(ref, source_hash)` 不覆盖 payload 值与文案 / 否 哈希渲染文本（UI 版本会钉进方法论台账）。
- 预算按**块**（`(track, object_type, derivation)`）整体省略 / 否 按键截断（今天 `_PAYLOAD_KEYS=6` 的做法，丢信息不留痕）。预算量纲用块数不用 token（token 随 tokenizer 漂，哈希会跟着模型漂）。
- 用户产品外手写的剧本允许无哈希，但必须显式 `user_authored=True` 并在记录里写 `projection_hash_missing=user_authored`、校准单列 / 否 一律拒收（会把 CLI `observation confirm` 无 `--from-slice` 的路径打死）/ 否 伪造一个哈希。
- 带读 v0 `budget=None`（不限块）：今天带读本来就渲染全部对象，只在显示键数上省；`omitted` 机制靠 `budget` 测试钉住。
- 新模块名 `river_projection.py`，不复用 `episode_projection.py`（那是 durable 事件投影，同名不同物）。

## 当前状态
代码 + 22 条新测试 + 收据已写；目标测试 156P（含既有带读 / 剧本 / checkpoint 套件）。真库冒烟 `半导体@2026-09-07` 两次 `cp:7b032c7bf5a758c1`。**干净树全量门禁读数见收据「门禁」节（合入前补跑）。**

## 未验证 / 已知边界
- 授课框架规则选择器未实现（G-01 后）；`selected_by` 恒 `default`。
- `RiverObject` 无 `hardness / derivation` 字段，投影从 payload 读，真库上硬度序全平局。
- 「上证指数」在 `river.slice` 里六轨 `entity_unresolved`（板块宇宙口径），冒烟用板块。

## 下一步
- 合入后：#37 情景树（硬依赖本单的哈希）；G-01 后把授课框架规则接到 `rules=`。
- PR #666 分支里回写 `UBIQUITOUS_LANGUAGE.md` 四条词（上下文投影 / durable 事件投影 / projection_hash / selected_by）与路线图 G-14「已落」。

## 踩过的坑
- `render_object(keys=RENDER_KEYS)` 用模块常量做默认值，测试里 `mock.patch` 常量不生效——默认值在 def 时就绑定了；改成 `keys=None` 运行时读。
