# 连板日历部署候选 · 2026-10-08

## 交付状态

已在现有 Workbench 完成后端修复、数据覆盖展示、交互完善、真实 API 浏览器测试与生产静态构建。**这是部署候选，不是生产已上线，也不是完整发布门禁已通过。** 工作分支 `arena/a3bfea49-finance`，基线 `82de3fb7`，本轮未提交/推送/合并。

### 本轮范围

- 前两项断板缺陷：按权威交易日历配对、不跨缺口推断；月初预读真实前一交易日，窗口大小不改变断板高度。
- 新增每日 `high_board_comparison_status`：`available`、`data_missing`、`calendar_unknown`、`not_applicable`。它仅表示两日名单可取得，不是供应商名单完整性证明。
- 日格明确显示“断板未判定”；汇总显示可比较天数。完全不可比较时事件数为 `—`，不冒充零。已识别事件保留，只汇总已识别部分。
- 月份直接选择、上/下月范围边界、成功后的主动刷新；失败可重试，切月份的过期响应不能覆盖新月份。
- 窄屏日历由外层横向滚动，避免中等宽度被内层 overflow 裁切；手机摘要改成两列，焦点可见。
- 复用现有“同日连板”入口；不另造 dashboard、不改生产数据库、不接新外部供应商。
- 已重建 `intelligence/api/static`，HTML 与哈希资源配套。

## 实际验证

| 范围 | 结果 |
|---|---|
| 后端 `test_board_calendar.py` + `test_trading_calendar.py` + 完整 `test_workbench_api.py` | **198 passed**，1 条 Starlette 测试客户端弃用警告 |
| 前端全量组件 | **22 文件 / 217 passed** |
| 既有 Workbench 全套浏览器 E2E | **52 passed / 2 skipped**（绑定链路仅跑 desktop，既有 tablet/mobile 两例跳过） |
| 新增连板日历真实 API 专项 E2E | **6 passed**；桌面1440、平板1024、手机390，各2例 |
| 全仓 Ruff、前端 ESLint、TypeScript、生产 Vite 构建 | 通过；构建有 >500kB chunk 提示，未宣称警告清零 |
| 最后手机摘要布局调整 | 调整后重新构建，并重跑日历6项E2E通过；之前52项Workbench E2E不移签为该CSS调整后重跑 |

专项 E2E 使用真实生产 API app 和完整 schema 的合成 DuckDB，不 mock 日历/梯队成功响应。覆盖月初6板、缺日不误报、展开/收起、门槛切换、刷新、日历→当日梯队、页面错误、外层滚动无内层裁切；另一例只中断网络以检验重试恢复。

Python 环境从最小环境补装了 `requirements-dev.lock`，本轮没有使用 `FWP_ALLOW_ANY_PYTHON`。实际 Python 为3.11，不等同正式锁定环境3.12，依然需要目标环境/CI复核。后端198项为三个文件，不是全仓Python。

本沙箱浏览器首次因缺 `libnspr4.so` 启动失败；通过仓外npm分发的Chromium及其运行库解决，随后去掉single-process参数解决上下文重建退出，最终6项全绿。浏览器版本为153，非Playwright默认捆绑版本；CI应继续使用 `playwright install --with-deps chromium`。中文字体仅装于沙箱，不随应用发布。全部截图、测试库、用户态在忽略的 `test-results` 下。

## 可重复测试

在仓根使用项目解释器：

```bash
.venv-workbench/bin/python -m pytest intelligence/tests/test_board_calendar.py intelligence/tests/test_trading_calendar.py intelligence/tests/test_workbench_api.py -q
.venv-workbench/bin/python -m ruff check .
cd intelligence/webapp
corepack pnpm install --frozen-lockfile
corepack pnpm lint
corepack pnpm typecheck
corepack pnpm test
corepack pnpm exec vite build
corepack pnpm exec playwright install --with-deps chromium
corepack pnpm test:e2e
corepack pnpm test:e2e:calendar
```

`test:e2e:calendar` 是独立服务端口8795，可通过 `BOARD_CALENDAR_E2E_PORT` 覆盖。`WORKBENCH_PYTHON` 可指定已配置的解释器。可选 `WORKBENCH_CHROMIUM_EXECUTABLE` 仅用于有自备浏览器的测试环境，生产不需要它。新增专项已接入 `workbench-check` 的 E2E 步骤；**本轮尚未推送，所以不能宣称远端 CI 已绿**。

## 发布前硬条件（未满足则不切生产）

1. 将本次日历代码、测试、CI配置、配套静态构建与文档送审；不要夹带 `crocodile-flight/` 或测试数据。仅使用本会话分支，不引入PR #75未合入的代码。
2. 在正式Python3.12锁定环境完成全仓门禁、收据范围/版本核验及该提交的GitHub CI。不能用本次198项替代全仓。
3. 在正式库**只读副本**上核对：普通连续交易日、跨周末/节假日、月初、两表缺口、未登记年份。名单缺失不能等同未涨停；需核验供应商完整性，不能只看有一行就宣布数据齐全。
4. 截止日按真实行情到货状态显示；选历史月时不要把顶部全市场新鲜度当该月已完整。期望板数与 API、日格、汇总逐一对齐。
5. 取得合并/部署授权，按 `docs/workflows/acceptance-workflow.md` 及实际运行快照方式发布。部署主机和生产库本轮未连接，未冒充上线验证。

## 部署与回滚

- **无schema迁移、无回填**：新字段是只读投影，不写事实表，不需要执行采集或导入命令。
- 后端与 `intelligence/api/static` 同版本发布；不可仅拷HTML或只拷新JS而丢CSS。旧后端未提供覆盖字段时，新前端保守显示未知，不能据此认定升级完成。
- 已有 standalone 部署脚本有真实副作用：仅在干净源码、精确完整SHA、已有正式环境和授权后调用 `scripts/deploy_workbench_runtime.sh --apply --expect-revision <完整SHA>`，显式指定 `WORKBENCH_REPO_ROOT`。Git快照不走覆盖脚本，按仓库验收工作流切运行指针。
- 发布前保存旧运行快照身份及指针；发布后核验实际运行代码/静态资源版本、健康接口、日历接口与梯队跳转。不能仅凭 Git 合并或一个健康版本号宣布已生效。
- 接口500、静态资源404、数据错位/跨缺口误报即停止推广，按既有流程切回旧运行快照；不删除原快照、不恢复或覆盖行情库。旧版本可能含已知断板缺陷，应同时暂停依赖该断板统计的使用。

## 预览

沙箱8796仅用于合成数据验收，与生产隔离。进入“连板日历”，选择 **2026-09**。所有示例个股名带“合成”，不构成真实行情。预览不是生产部署，且不会持久保证进程在线。
