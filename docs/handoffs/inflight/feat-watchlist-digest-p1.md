# 在途交接 · feat/watchlist-digest-p1

更新：2026-08-27 03:10 CST · **P1 三件齐（发酵摘要 / 快照证据页 / skill 软链），未合并**。基 `gitea/main`=`990c1c86`（含 P0 已切生产 27a），树 `/Users/a77/fwp-wt-wd-p1`。台账预注册 `R-20260827-01/-02/-03`（落表时验证过 gitea/main 无今日占用；若合并前被别的 session 占号，按 `R-20260824-31` 先例改号）。

## 三件的形状

- **P1a 发酵摘要**：新模块 `intelligence/services/theme_fermentation.py`——`trace_sectors_fermentation` 批量纯函数；逐交易日委托 `market_watch_pack._query_dual_red/_query_limit_heat`（与简报接合同一份袋口径，LIMIT 截断 → 措辞「在袋/在榜」）；自有 SQL 仅交易日历（fact_market_daily），口径棘轮有机械钉。触发面严格 spec §3.3：**theme 项 × (主线|严格双红) 命中**才挂；个股项、仅热度命中不挂。摘要行进公开稿「清单命中」段（主体块之后），数字 ⊆ 快照新键 `fermentations`；瘦收据加 `fermentation_rows`。
- **P1b 快照证据页**：`DigestSnapshotView.tsx` 只读渲染（方法卡/清单/四袋状态表/接合行/发酵摘要/袋行明细 JSON），挂在 MessageBubble（`report.watchlist_digest_snapshot` 存在才出现）；类型加在 `types.ts`。数据通道零新增——`/api/runs/<id>/report` 本来就回整份 report.json。
- **P1c skill 软链**：`skills/watchlist-digest/SKILL.md`（**只做入口指针**，明文声明不复述口径）+ `.claude/skills/watchlist-digest` 相对软链 + 注册表 scan（59→60）+ CLAUDE.md 生成块自动补行。

## 测试收据（离线）

- `test_theme_fermentation.py` 7 钉先红（ImportError，`20260826T184918Z-990c1c86`）后绿。
- pack 27 钉（24+3 新）：触发面 / 单次批量委托 / 停机路径空。34 过收据 `20260826T185151Z-990c1c86`。
- 前端 lint+typecheck+69 过（67+2 新：证据页可点只读、无快照不渲染）。
- 注册表四检查 CI 语义 rc=0×4（REPOS_DIR 补丁指向本树；本地原生跑会读主检出树的 skills，主树未 pull 前会假红——这是 build_registry 按固定仓名解析根的已知形状，不是漂移）。

## 已知边界

- 发酵摘要的 live 触发依赖当日数据：清单 theme 若只命中涨停热度袋（如 08-26 的人工智能/工业互联）则**不挂**摘要——这是 spec 触发面，不是缺陷。
- 快照证据页只在确定性简报回合出现；旧 run（P0 切流前）的 report 无 `fermentations` 键，页体容忍缺键。
- 8792 现役 `67c88b27`（27a，含 P0 不含 P1）；P1 合并后需再切一次才上生产，夜跑代码路径（market_feature_store sync）P1 零改动，二次切流不影响今晚 18:30 `R-20260826-04` 判据。
