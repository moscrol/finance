# 既有 Workbench UI 恢复记录 · 2026-10-03

实现提交：`03bb662d078e6e0065bc1196b7140156aed9c1d2`。基线为 PR24 的 `bd0be25db7b5ed04d12a86ed6f726aaf4fda3e04`；所有写入都在 `fix/workspace-ui-closeout-1003` 的独立工作树中完成。尚未推送、独立审查、合入或部署。

## 背景与来源

2026-09-29 的原版 8798 优化、日报阅读页与观察工作区已经存在，但当前 App 没有挂载这些组件，配套 API 也未注册。2026-10-03 用户授权完成既有优化、质检合入和部署，覆盖旧手册当时的暂不发布边界；实施子任务只交付源码提交，总整合者负责发布。

先阅读原规格与恢复来源，固定哈希后再迁入：

- `feat/board-calendar` 的 `cfc68ea05af3be8eb251e712ad4d0515a2ae2e86`，另比较其未提交服务、组件和回归测试修补。
- 主检出树未提交的 River、daily-review、opinion-attention 和 observation 源码。依据 `2026-09-29-original-8798-optimization.md`、`2026-09-29-daily-review-dashboard-implementation.md`、`2026-09-29-agent-consumption-observation.md` 与 `inflight/arena-river-opinion-0929.md`。
- `feat/workbench-tech-premium@717d243be` 的主题状态、样式及两个效果组件。
- 逐文件 SHA-256 见 [source-hashes.json](../verification/workspace-ui-closeout-1003/source-hashes.json)。迁入前与提交前共 64 个来源文件复核一致；来源树始终只读。

## 发现顺序与处理

1. 月历提交能干净应用；随后迁入其真实脏增量，保留交易所休市、未来、市场缺口和连板缺口的不同状态、严格日期校验与窄屏规则。
2. 当前 App 已包含更新的会话、研究运行和导航逻辑，因此只增加月历、连板、长河入口与共享 `marketFocusDate`。长河内部恢复每日复盘、观察验证、六轨、公开消息入口；没有替换 App、main、Vite 配置或旧静态包。
3. 复用原组件的日期请求取消、请求序号、历史窗口、最新重新锚定和旧图清理规则。日报继续读取同日归档，缺失日明确为空；观察冻结条件、追加复查、生成核验问题和导出保存在本浏览器，未接入模型调用或正式学习台账。
4. 发现原 `opinion_attention_bridge.py` 没有接入 `slice_river`。总整合者明确确认恢复该原有意图后，接入独立的 `public_news_attention` 对象；原研报对象继续保留，若研报缺失则在公开消息对象附上原 `report_coverage_gap`。公开消息可见性仍受 `min(as_of, knowledge_cutoff)` 限制，不因 hindsight 放宽。
5. 发现旧连板时间窗会把无源行的交易日算成 0。现在保留 `data_status=missing` 与 nullable 总数／高度，图线断开、梯队显示“缺”，缺失前日不推导晋级率，窗口均值缺覆盖则为空；最高值明确标为已记录最高。
6. 科技主题作为持久化可选项接入，默认仍为暖纸主题。存储失败、无 matchMedia、减少动态效果偏好均有回退，动画标题保留稳定可访问名称。
7. 真实浏览器发现顶栏原有 CSS 优先级使主题按钮挤出视口；修正 flex 选择器，窄屏标题和连板控制栏可换行。截图又发现旧主题的通用按钮底色覆盖连板选中态，补上限定于该控件的选中态规则及浏览器断言。

## 决策与被否方案

| 方案 | 评价 | 结果 |
|---|---|---|
| 当前 App 上逐项迁入旧功能 | 保留 PR24 的会话交付、研究进化和取消恢复逻辑 | 采用 |
| 用旧 App 整文件覆盖或使用独立离线看板 | 会退回新功能，违背原版工作台入口约定 | 排除 |
| 无源行保持未知，已知真实 0 仍为 0 | 无采集覆盖证据时不能断言当日零连板 | 采用 |
| 用空列表、0 或最近日期补齐 | 会伪造历史表现和窗口均值 | 排除 |
| 桥接公开消息对象且保留研报缺口 | 恢复已有适配器意图，传播与研报覆盖仍可辨认 | 采用 |
| 把新闻热度加到研报份数或补真实新闻 | 改变口径并引入未授权采集副作用 | 排除 |
| 原主题作为用户可切换选项 | 复用兼容的既有用户设计，保留原默认外观 | 采用 |
| 旧主题分支 App、生成包、预览桥整体迁入 | 混入过时入口与专用验证环境 | 排除 |

未迁入 FinArena、预览水印／main／bridge／Vite 配置、`LimitUpCalendarDashboard` 的静态 JSON 替代设计、生产 public 数据、真实日报归档、私人用户目录或独立 staleness 分支内容。`opinion_attention.py` 保留原有离线适配与台账写入函数及其测试，但本轮新增 API 全部只读，未迁入新闻导入脚本，也未调用这些写入函数处理真实数据。

## 验证与可用结论

以下检查针对实现提交中的同一份源码，在提交前完成；Python 收据会显示基线 SHA 加 dirty 状态，不能冒充该提交的全仓干净收据。全仓精确提交发布门禁由总整合者执行。

| 检查 | 结果 |
|---|---|
| 最终定向后端 13 个文件 | 258 passed / 35 skipped / 1 Starlette deprecation warning；39.31s |
| 改动 Python 的 Ruff | 通过 |
| 前端 lint、typecheck | 通过 |
| 全部前端组件测试 | 18 文件、178 passed |
| 前端构建 | 通过；JS 544.20 kB，gzip 167.90 kB；单块超过 500 kB 提示仍在 |
| 完整现有 E2E + 新恢复入口 E2E | 桌面／平板／手机合计 43 passed / 2 skipped；1.3m |
| 最后一条主题对比度 CSS 修补后的 River E2E | 三端 9 passed；23.3s |
| 提交钩子 | Ruff、层级、路径、正则、字段、数据集、工具可达性与目录保鲜均通过 |

后端文件：`intelligence/tests/test_board_calendar.py`、`test_workbench_api.py`、`test_river_routes_registered.py`，以及 `tests/test_limitup_history_window.py`、`test_river_daily_overview.py`、`test_river_daily_review.py`、`test_opinion_attention.py`、`test_river_slice.py`、`test_river_query.py`、`test_river_range.py`、`test_river_cutoff_guard.py`、`test_river_frozen.py`、`test_river_recorded_at.py`。

收据：`~/.finance-runtime/test-receipts/20261003T050622Z-bd0be25d-724fbcd38a30.json`。35 个跳过来自既有真实市场库依赖测试；该独立树未放置生产库。新增桥接集成测试使用临时完整 schema，验证确定性、时间截止、研报缺口与 DB 文件哈希不变。

工作树本地日志在 `.tmp/workspace-ui-closeout-1003/{backend-final,frontend-final,build-final,e2e-final,e2e-theme-final}.log`。日志、收据、来源哈希和截图另存于工作树外的 `~/.finance-runtime/verification/workspace-ui-closeout-1003/`，供后续精确版本审查使用。最后三端截图在 `intelligence/webapp/test-results/river-*/`，均为合成夹具。E2E 用真实 App 和隔离 FastAPI 服务，市场响应由合成 reader fixture 提供；原会话、SSE、取消、深挖和研究进化现有用例仍执行。观察用例验证冻结后重载、追加复查、导出 JSON 等于原记录，并断言没有模型写请求。

初次完整 E2E 为 39 passed / 4 failed / 2 skipped：1 个来自未设置 `RE06_E2E_URL` 而访问默认端口，3 个来自主题按钮在视口外。原 CSS 失败截图与上下文保留于 `.tmp/workspace-ui-closeout-1003/e2e-before-css/`；修正配置与样式后才得到上表结论。不能抹去失败或描述为首跑全绿。

本轮使用总整合树锁定的 `.venv-workbench`（httpx 0.28.1），未改共享虚拟环境。`FWP_WORKBENCH_PYTHON` 用于提交钩子解析；E2E 使用 `WORKBENCH_PYTHON`。E2E 端口 19071 / 19074，同时设置 `RE06_E2E_URL=http://127.0.0.1:19074`。构建只写本树静态目录，跑完后恢复基线三个受跟踪静态文件并删除本轮生成的两个新资产；提交中无 `intelligence/api/static` 改动。再次 E2E 之前须先 `pnpm build`。

## 剩余与沉淀

- 接下来依次做独立规格审查、质量审查、修复回归，再由总整合者执行全仓精确提交门禁、PR、合入和部署。
- 不能把合成浏览器测试当成真实日报／真实消息完整性、生产 API 已加载、模型研究质量或严格历史回测的结论。本轮无真实新闻导入、无抓取、无真实模型调用、无生产 DB 写入或服务重启。
- 浏览器观察记录沿用原来源设计，仅本地保存；没有新接正式 checkpoint／学习台账。真实 AIHOT 输入仍待接入，页面如实显示该状态。
- 本轮可重复的保护已落到后端／组件／E2E 测试。来源哈希核对与路径清单是这次源码回收的证据操作，依赖具体来源语义，不另建通用脚本或改共享 harness 仓。
