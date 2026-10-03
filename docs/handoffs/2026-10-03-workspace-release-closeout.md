# 工作区优化收口与正式发布 · 2026-10-03

更新：本轮可交付工程已通过 GitHub PR #24、#25、#26 合入并部署到 8792。实际运行版本为 `45a7dcfc219f70fce58c17a7487d05e6c969f403`，切换记录时间为 `2026-10-03T08:00:26Z`。最终主干的本机完整门禁、GitHub 五项检查及发布后真实会话验收通过。本文只记录已发生的验收与切换；后续文档提交不改变已验收的运行版本。

## 背景与发现顺序

用户要求盘点工作区与 GitHub，将无人接手的优化完成质检、收口、合并和部署。pi 正在进行的 `feat/harness-output-provenance-1003` 及其 plan-ownership 依赖保持独立，未改动其源树。盘点覆盖 74 个既有工作树、446 个本地引用、26 个 origin 引用和 601 个 Gitea 备份引用；引用数是盘点时点读数，不是合并完成判据。

1. 从最新 GitHub 主干集成有效回答工程和 harness 合同。恢复任务/材料/历史身份、证据授权、截止与预算、取消及可观测性；保留可选功能的原默认值。修复发现的证据阅读记账等问题，拒绝借工程通过重新启用已经否决的语义实验。
2. 独立恢复评测截止、工具预算下传、只读预检、冻结评分器、有限内容量具，以及消费/股价缺口/工具差分审计器。消费审计输出不能覆盖输入 DB，包括同路径、软链和硬链。私人 cohort 的 747 个运行路径及历史不完整版本映射没有进入公开仓。
3. 从原预览和未提交源中恢复月历、连板、长河六轨、日报归档、观察和主题界面。保留来源哈希；两轮独审修复数据缺口仍画收益、基准错位、未知数值变零、资金口径混算、日期回退、净值跨缺口连线、换码错配、浏览器并发写入和归档加载耦合。
4. 发布预检发现夜跑会把日志/质检/增量备份写入代码快照，开发依赖锁也不覆盖 AkShare 和日报绘图。补齐数据根解析与可选夜跑锁，在独立环境验证依赖和真实临时库导出。
5. 旧积分测试把固定日期额度与实时时钟比较，在 10 月 3 日到期，造成候选与 GitHub 同样两项失败。仅给测试 helper 默认注入既有固定时钟；生产到期逻辑保持原样，独立到期边界验证仍为 40 → 0 → 0。旧红收据保留。
6. 三张 PR 全部通过后，对实际合并主干重新做完整门禁，再创建独立代码/依赖快照。全用户持久化任务和内存队列确认空闲，停止旧服务后再次确认无待恢复任务，才切换 8792 与三个夜跑入口。

## 合并与验收身份

| PR | 固定候选 | GitHub 合并提交 | 本机完整 Python |
|---|---|---|---|
| [#24](https://github.com/moscrol/finance/pull/24) | `bd0be25db7b5ed04d12a86ed6f726aaf4fda3e04` | `f0328ae9b788f94c56040b3c3b6e7320dcfbe648` | 19,752 通过 / 78 跳过 / 2 预期失败 |
| [#25](https://github.com/moscrol/finance/pull/25) | `f6ed63ce1fca1b505d2f80c60ea3edcd61589fab` | `22950660b9c4affaa36d9c456e972a22dce95fd3` | 20,041 通过 / 76 跳过 / 2 预期失败 |
| [#26](https://github.com/moscrol/finance/pull/26) | `82fcaa989bb8cf196a8dad67c57a73b3ca6372a5` | `45a7dcfc219f70fce58c17a7487d05e6c969f403` | 20,146 通过 / 76 跳过 / 2 预期失败 |

三张候选均有固定版本的独立规格/代码质量审查、前端六阶段、注册表和 GitHub 保护检查。旧源 PR 已自动合并或在关闭前留下接替指针/废弃理由；没有删除源分支，也没有把 Gitea 备份旧枝批量恢复到 GitHub。

实际部署主干 `45a7dcfc219f` 的验收：

- Ruff 与全量 Python：20,144 通过、78 跳过、2 预期失败，收集 20,224 条；收集范围未收窄，收据与读数、解释器、依赖、干净树、完整 SHA 对账通过。
- 候选与主干的树内容相同。通过数净少 2 是原有代码地图条件用例：有图树跳过 3 个空图用例、运行 1 个结构探针；无图树反过来。四条用例按相应状态独立复核通过，未改 skip 条件或移签收据。
- 前端六阶段全部通过：195 项组件测试，52 项 E2E 通过、2 项既定跳过；起止身份及六份日志的长度/哈希核验通过。注册表 5 项通过。
- GitHub 主干 `workbench-check` 运行 `37106886922` 的 python/frontend/e2e/聚合均成功；`registry-check` 运行 `37106886870` 成功。没有触及条件 data-quality workflow 的路径。

主干 Python 收据：`~/.finance-runtime/test-receipts/gate-LPIZtddd/pytest.json`。其余原件位于 `~/.finance-runtime/reviews/workspace-closeout-1003/`，主要索引为 `final-main-acceptance.json`、`final-main-frontend/frontend.json`、`final-main-registry.json`、两份 `final-main-github-*.json`。候选与红灯收据按原版本另存，没有覆盖。

## 实际发布结果

代码快照：`~/.finance-runtime/finance-workspace-45a7dcfc219f`；运行软链指向该目录。快照含自己的 `.venv-workbench`，按开发锁及 `requirements-nightly-macos.lock` 安装，doctor ready、pip check 通过。新环境 49 项相关测试通过；禁网导入采集模块及合成绘图通过。前端在快照重新构建后与提交字节一致，发布后 Git 树仍干净。

工作台 launcher 仅替换 uvicorn 解释器；三个夜跑任务更新代码/解释器路径，其中 sync 同时更新 `FINANCE_S7_ROOT`。数据根、用户根、KB/RAG 配置、`REVIEW_SYNC_PLAN=local` 与原日程均保留。配置包原件和候选以私密权限保全，安装按 manifest 恢复文件模式，三个夜跑重新加载后均空闲，没有为验收手动执行同步或 finalize。

线上证据：

- health 的完整 revision 正确，`source_dirty=false`、`code_matches_repo=true`，`code_root` 是新仓根，`loaded_code_root` 是其 `intelligence` 包目录，`python_prefix` 是新快照 venv。ready 全部检查为 true。
- 通过真实 conversations/messages 入口完成一条个股快速事实查询。回答价格、涨跌幅、成交额与只读查询一致；数据日期为库内最新 `2026-09-30`。轨迹口径为 `fact_stock_daily`，包含真实列名；公开数据集别名为 `stock_daily`。
- 该次会话 completed、语义检查通过，degrade/content-degraded/judge-unavailable 均为 0，secret/public scan 均 0 命中。这是一个发布烟测，不证明复杂财务推导或整体模型质量提升。
- 生产 HTML/JS/CSS 与新快照逐字相同，8 个只读界面接口返回 200。部署账本 check 与 homes 通过，新 switch/startup 对上实际运行版本，旧家无账本遗留。
- 本次切换和探针前后，生产 DuckDB 的 inode、大小、mtime 不变。此前休市日派生快照的小 JSON 修复有单独收据；没有以休市日标签写入行情库。

对应证据为 `production-after-health.json`、`production-after-readiness.json`、`production-grounded-smoke.json`、`production-grounded-evidence.json`、`production-ui-api-smoke.json`、`production-installed-config-verification.json`、`production-ledger-check-v2.json` 与 `production-ledger-homes.json`。首次核验把包目录误当仓根、首次账本命令传根 URL 的检查错误均保留；修正核验参数后通过，不改服务结果或历史账本。

## 决策与被否方案

| 采用 | 未采用 | 理由 |
|---|---|---|
| 按来源/依赖择取有效工程，固定提交独审与完整门禁 | 整树覆盖、看分支名批量合并 | 旧树混有已否决试验、私人记录和较旧合同 |
| 保留工程结果与内容失败各自证据 | 用 CI 绿灯改判旧内容失败 | 评分器、预算和可观测性通过不等于金融推导正确 |
| 只保留数字列表标签的有限修复 | 短日期数字遮罩 | 955 条可重建历史回放出现额外误报；11 条不支持的输入也没有冒充通过 |
| 独立、受开发锁约束的夜跑环境 | 复制或升级共享主树 venv | 共享环境的 mootdx 约束与锁定 httpx 冲突，且 pi/既有运行在用 |
| 数据与运行产物写配置的数据根 | 让夜跑写不可变代码快照 | 防止运行污染版本身份和备份落入待淘汰快照 |
| 停服务后再核对持久待恢复状态 | 只看默认用户内存计数 | 启动会扫描所有用户并恢复 queued/running |
| 保留旧快照和配置原件 | 覆盖旧运行目录 | 可按明确版本回滚，保留真实 switch 记录 |

## 留存边界与后续

FinArena 按此前用户确认的归档决定保持归档；没有恢复 8816 或重新启用正式参赛。材料 excerpt/redraft、JSON-wire/提示词、按模型强弱硬分流等被否决或未通过的试验没有借此次发布变绿。目录投影仍为评测专用、默认关闭；evidence_read 等可选工具保留显式授权与原默认值。工具差分原严格样本验收不因量具入库而被宣布完成。历史统计/内容台账保持原裁决。

观察记录保存在同源浏览器，不跨设备；Web Locks 保护同名锁参与者，锁不可用或保存失败时明确未保存并可导出。JS 约 546 KB 的构建体积提示保留。

三个夜跑入口已部署，但本轮只做路径、依赖、临时数据和配置验证，没有触发真实写库夜跑。外部 S7 staged wrapper 仍保留旧 stat/probe 编排，其调用没有 `expect_identity`；不能声称自动取得 native daily-full 的整段并发锁保证。失败告警及知识库接收仍有既有跨仓代码/解释器边界，详见仓外 `deployment-plan-review.md`。

回滚原件位于私密 `deployment-config-45a7dcfc219f/`；旧运行快照 `finance-workspace-2c3949786568` 保留。后续判断新任务是否已落地用 `scripts/worktree_board.py` 和实际 GitHub/health 状态，本文固定记录本次观察，不作为长期动态看板。

工具沉淀：本轮可复用的审计器、预检、路径修补及回归已进入源码。部署配置生成/状态扫描/冻结材料对照脚本含本机路径或本次输入，原件留私密证据目录；没有包装成通用产品接口。没有新增证据支持改变既有模型质量、样本有效性或历史金融判断。
