# fix/episode-slot-fill-numbers

## 这个分支做什么
子单 B：必填格数字从预取行填入。九刀覆盖预取/判官/repair/数据层；live 仍未进 episode 引擎。

## 当前状态
干净树从 `gitea/main`@`dfc25221` 长出。**22 笔未推**（含质检 1 笔）。工作树干净。
九刀：1 预取观察值 `98a02774` → 2 删句记缺口 `1384a33a` → 3 槽补真值 `fe8555e0` → 4 数值门禁认观察值 `83f671ce` → 5 核对从判官拿走 `794d2acb` → 6 不可达投递 trace `135354c1` → 7 同日多行标口径分歧 `11731551` → 8 缺口按丢失原因分流 `907f2938` → 9 撞名棘轮审计 `cb91fa73` + VIEW 口径 `6d32a715`。
一次回退：`f552946b`（「不可达」升级为跳过修复轮，判据看不见 salvage）。

## 未验证 / 已知边界
- **live 未进 episode 引擎**：手搭 sidecar 与生产不等价，读数作废。别再手搭；先解 `scenario_tree` 预检在非生产环境必败。
- 槽只在 judge repair 路径补真值，正常写稿路径未消费 `observation_value`。
- `agent_episode.py`「否则删去数字」仍在提示词，归子单 C。
- `dual_red_counts` 预取行还没出 observations。
- 审计未接 daily-full；worktree 无 db/ 时跳过并明说「不是通过」。
- gitea/main 存量红：prefetch 事件未进 `DURABLE_EVENT_KINDS`（另案）。

## 下一步
1. live 验九刀——先有能进 episode 的 sidecar，不要再手搭。
2. prefetch 事件登记进 durable-kind 表（main 存量红，可顺手）。
3. `audit_sector_name_collisions.py` 接 daily-full 收尾（手跑 → 同步后跑）。
4. 合入等用户确认；**未切 8792**。

## 踩过的坑
- **重叠 ≠ 代码数**：换代两段不重叠不报；按代码数判会永久红灯。
- **读 VIEW 不读 generation**：物理表分代同日多行是快照，不是撞名。QC 前 PCB 27→VIEW 25。`check_sector_fact_access` 拦名单外读物理表。
- 撞名不进 pre-commit：由写数据引入，commit 时拦错对象；worktree 无 db/ 会天天误红。
- 引用卫生 ≠ 真伪判据。不要给含真值的句子免死金牌。
- 「某条路走不通」≠「整件事做不了」（`f552946b`）。

## 已验证
第 9 刀 QC：41 passed；层门禁 0 违规；红队 摘「钙钛矿电池」认出新增、小金属 100→406 认出恶化。基线 128 名，VIEW 口径 PCB=25 / 钙钛矿=24 / 小金属=406。
