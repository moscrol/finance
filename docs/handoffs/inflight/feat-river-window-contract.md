# 在途交接 · feat/river-window-contract（工单 #35 / G-02c）

## 这个分支做什么
把区间做成与单点同级的契约：`river_window_contract.window(start, end, entity, C)` 返回保留对象身份的切片序列 + 可拆回天与行的派生对象，整段 `pit_grade=min`；`river_derive` 五类派生（streak / transition / cumulative / first_event / signature）带 `gap_policy`；`river_anchor.anchor_windows` 是 slice+window 的组合（§4.6）；三个绕过 PIT 的读数（`build_daily_vectors` / `market_regime_analogs` / `range_aggregate`）接上 `knowledge_cutoff` 出 `pit_grade`；前视棘轮测试。收据 `docs/verification/2026-09-08-river-window-contract.md`。

## 决策与被否方案
- 模块名 `river_window_contract.py` / `river_derive.py` / `river_anchor.py`，否 工单写的 `river/window.py`——`river.py` 是模块，同名目录会遮掉它。
- 区间内每天用同一个 C 取片，再把 `hindsight` 改成区间级（C > end 才算）/ 否 逐日各用当天当 cutoff（那是逐日重放不是区间）。
- 向量 PIT：当天**没有行**的源是维度缺口不参与判定 / 否 一律降档——资金轨只有 51 天会把其余 360 天全判降档，读数没分辨力（第一版就是这样，真库 27 strict；改后 381 strict / 34 降档，降档全是被日更 60 天窗重写的近期）。
- `range_aggregate(knowledge_cutoff=None)` 保持老形状不写 pit 字段 / 否 默认 C=end 并出 pit——会改所有既有调用方的 to_dict。
- `leader_succession` 接 river 上下文做成 opt-in（`river_db_path`）/ 否 默认开——`river_entity` 默认「上证指数」在 river 里解析不出（板块宇宙口径），开了只会全是 `river_enrich_error`。

## 当前状态
14 新测试 + 邻近套件 122P；真库 `半导体 2026-08-24→28` 两次哈希相同、切片 5/5 等于 `slice_river(day, C)`（hindsight 归一后）、四类派生全 ok；`build_daily_vectors(C=2026-09-05)` 415 行 381 strict。**干净树全量门禁见收据（合入前补跑）。**

## 未验证 / 已知边界
- `derive_signature` 无单测夹具；`anchor_windows` 的事件到事件 lookback 未做；`teaching_framework.py` 未传 `river_db_path`。
- 表无 `recorded_at` 列，PIT 用 `updated_at` 作上界。
- 事件定价迁移归 #663；`market_analogs` / `stock_analogs` 只受「不新增裸扫描」棘轮约束。

## 下一步
- #37 情景树需要历史标签时改用本单的 streak / transition 派生对象（`analog_ref` 也从这里来）。
- river 接指数实体后把 `river_entity` 默认改回「上证指数」并在 `cmd_build_succession` 开 `river_db_path`。

## 踩过的坑
- 单点 `slice_river` 的 `hindsight` 判据是 `C > as_of`，区间里每天 C > day 都成立——不改标记会让整段永远 trade_date_only。
- pytest 命令行里带一个不存在的测试文件路径，整批「no tests ran」而不是报错——别把别的分支的文件名带进来。
