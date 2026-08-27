# 在途交接 · feat/public-daily-brief

更新：2026-08-27 17:45 CST · **P0 完成（spec + 包 + CLI + 测试 + 真库冒烟），PR 待建/待合，未动 8792**。

## 状态

- 分支 `feat/public-daily-brief`，基 `gitea/main`=`470e43a3`，树 `/Users/a77/fwp-wt-public-brief`。
- spec：`docs/superpowers/specs/2026-08-27-public-evening-brief-design.md`（骨架=数据许可白名单：公开事实 + 自家 KB 加工可出，供应商派生口径一律不出）。
- 实现：`intelligence/services/public_brief_pack.py`（纯函数，委托 `run_market_watch_pack` 取数、只渲染 market 袋白名单字段；连板段包内精确日 SQL；题材段解析当日 `<date>-theme-candidates.md` 前 3、不读触发列）+ CLI `python3 -m intelligence.cli brief`（HTML 必出，`--png` Chrome 无头尽力而为，`--write-snapshot` 落 `~/.finance-runtime/public-brief/`）。
- 产物是文件不是题型：零路由改动（台账 `R-20260827-09` 锁回归）。

## 测试收据

- 定向 `test_public_brief_pack.py` 8/8 绿（收据 `20260827T093544Z-470e43a3.json`）。
- 变异击杀 2/2：白名单准入放行全部键 → 单元锁红；渲染层塞「市场阶段」行 → deny-token 红；还原后 8/8 绿。
- 真库只读冒烟（2026-08-26）：deny 扫描零命中；+0.59% / 3912 / 18,084 亿 / 52 头 0 / 2946 五组数字逐字对库；HTML+PNG 出货（视口 750×1250）。
- 全量套件读数随 PR 评论。

## 未做（点头再做）

- P1：晨报（外盘+事件日历，公开引用口径先换自取源）、发酵叙事公开版、卖方覆盖密度统计段、夜跑挂点（与 watchlist-digest P2 共用时槽、产物分开）。
- P2：自动分发（公众号/静态站点）、视觉头图模板。
- Live：合并后用户复核最近交易日产物观感与口径（台账 `-07` 行，执行方不自标 confirmed）。

## 已知边界

- 题材段素材=当日 theme-candidates 产物；当日工作流没跑 → 整段缺口句（不是 bug）。
- 连板表天然稀疏：无该日行 → 缺口句，不借邻日。
- PNG 固定视口 750×1250，内容极端加长会截底（当前布局稳定 ~950px）；HTML 是主产物。
- 产物 `复盘/briefs/<date>/` 不自动 commit，提交与否由人决定。
