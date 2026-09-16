# 飞书整体退役（分支 `chore/retire-feishu`）

一句话：**飞书的代码全删了，数据先导出了，告警换成本机通道；剩最后一步要你亲自做——到飞书开放平台把自建应用删掉。**

## 为什么敢删（先量后删，不是凭印象）

| 证据 | 数字 |
|---|---|
| 8 张 Bitable 表最后一次写入 | 大成交 2026-05-08、强势股 05-20、板块趋势 05-19、连板晋级 06-03、板块涨幅成交额 06-03、涨家数走势 06-18、每日指标 06-18（自选股无日期字段，人手维护） |
| 距退役日 | 约 3 个月无人写 |
| launchd 里的飞书作业 | 0 个 |
| 昨夜复盘链的飞书步骤 | 0 个（步骤全是 `-local` 变体） |
| 唯一还在调的 `notify_feishu` | **每次 HTTP 400**（token 换得到，`GET /im/v1/chats` 缺 `im:chat` 权限）→ 告警从来没送达过 |
| 本地 vs 飞书数据 | 本地是超集，例 `fact_market_daily` 404 行 > 飞书「每日指标」159 行 |

唯一没有本地副本的是**自选股那 13 只**——它只在飞书里由人手维护。

## 删之前先备份了

- `~/.finance-runtime/feishu-export-20260911/`：8 张表全量只读导出（板块趋势 1875 / 每日指标 159 / 涨家数走势 160 / 自选股 13 / 强势股 62 / 连板晋级 214 / 大成交 60 / 板块涨幅成交额 228）
- `~/.finance-runtime/retired-feishu-20260911/`：两个夜跑脚本改动前的副本 + `feishu_config.json` 副本（0600）

> 自选股 13 只若还想用：清单在导出目录里；本地对应的能力是 profile 的 `watchlist` 字段
> （`intelligence/services/watchlist_digest_pack.py` 从画像读清单）。**要不要钉进画像是你的决定，我没动。**

## 三个提交

1. `a8f2d0a4` **告警通道换本机**：新增 `scripts/notify_ops.py`（`~/.finance-runtime/alerts.log` 追加一行 + macOS 弹窗，零网络零密钥），删 `scripts/notify_feishu.py`，改 6 处调用点。语义保持不变（返回 True/False、异常不外抛、CLI 退出码 0/1），调用方一律 `|| true` 兜底。
2. `2f8dbf3e` **删飞书全部代码路径**（下表）。
3. `607e4efb` **测试跟上**：删 `tests/test_limit_advance_write.py`（被测脚本没了）；`test_code_map.py` 的门旁退役标记断言改为认「退役」（措辞随 CLAUDE.md 改口）。

### 删了什么

| 类别 | 内容 |
|---|---|
| sync | `market_feature_store/sync/sync_feishu_*.py` 五个 + CLI `sync-limit-advance-feishu` |
| IM | `intelligence/chat/feishu_bot.py` + plist + test + CLI `feishu-bot`（退役闸一并收走） |
| 图表 | `skills/advancers-chart` 整个 + `sync_daily_full` 的 `advancers-chart` 步与 `chart_table` / `with_chart` / `--no-chart` |
| 纯飞书 skill | `top-gainers-feishu`、`up-line`、`watchlist-ma`、`sector-data` |
| 混合 skill 只删飞书脚本 | `market-overview`（check_coverage / verify_and_patch / feishu_write.md）、`high-volume-gainers`（write.py）、`limit-advance`（write / check_coverage / dedup_fields） |
| 文档 | `CLAUDE.md` 飞书表与凭证段重写、`skills.registry.json`、`dispatcher` 路由表、`runtime-and-pitfalls.md` 飞书段重写 |

### 特意没删的

- `intelligence/dream/collector.py` 的 `normalize_feishu_event`：只解析**已归档**的 transcript 文件，不联网、不拿密钥。
- `scripts/agent_review/contract.py` 里的 `"feishu_config.json"`：那是**禁止提交**的黑名单，是防线不是读取点（门禁已对它开白）。
- `intelligence/eval/cases/ceiling_instruction_allowlist.json`：记着已封存实验的输入指纹，改它就动了库尾答案。**其中 5 条路径现已不存在**，下次重建该 fixture 要重新选面——这是本次留下的唯一已知欠账。

## 能力没丢，换了地方

| 原飞书链路 | 现在用什么 |
|---|---|
| 每日指标 / 市场总览 | `daily-full` → `fact_market_daily`；skill `market-overview`（本体保留） |
| 板块趋势 / 边际量 | `sync_fupanhui_sector_daily` → `fact_sector_daily` |
| 连板晋级 | `sync-fupanhui-limit-advance-daily` → `fact_limit_advance_presence`（本来就是它在写，没成孤表） |
| 涨家数走势图 | `daily-review --chart-output`（本地 PNG，早就是它在出图） |
| 强势股 / 大成交排行 | CLI `interval-gainers` / `weighted-gainers` |
| UP 线与偏离度 | `market_feature_store/query.py` 的 `ma26 + 0.764*std26`，与原 skill 同一公式 |
| 运维告警 | `scripts/notify_ops.py` |

`sector-data` 里三条与飞书无关的 fupanhui 抓取坑（CDP 用 `fetch()` 非 XHR、`sectors/search` 的 `strength` 不是成交额、universe 必须取当日 `ts_code` 否则像 `PEEK材料` 那样漏填）已搬进 `docs/data-sources/runtime-and-pitfalls.md`。

## 防回潮

新增 `tests/test_pipeline_p0.py::test_no_module_reads_feishu_credentials`：仓内（已跟踪文件）不得再出现 `feishu_config.json` / `tenant_access_token` / `FEISHU_APP_SECRET` / `feishu_utils` 的读取点。
**已过变异**：临时加一个读凭证的文件 → 变红；删掉 → 变绿。

## 仓外改动（不在这个 PR 里，已就地改完）

- `~/.local/bin/nightly-full-review-s7.sh`：与仓内版本逐字相同，整份同步。
- `~/.local/bin/nightly_full_review.sh`：**本机版与仓内版有其它有意差异**（L2 源说明、`DATA_ROOT` vs `CODE_ROOT`），只就地改了飞书那两行，没覆盖。
- 两份改前副本都在 `~/.finance-runtime/retired-feishu-20260911/`，`zsh -n` 语法自检通过。

### 告警三条腿的真实状态（合并后复核，订正上文）

| 腿 | 依赖 | 状态 |
|---|---|---|
| 桌面弹窗 | 无（两个夜跑 shell 的 `notify()` 第一行就是内联 `osascript`） | ✅ **一直是通的**，从没断过 |
| 落盘 `alerts.log` | `$DATA_ROOT/scripts/notify_ops.py` | ⏳ 等 `$DATA_ROOT`（主检出）更新到 main 才生效 |
| 飞书 | 网络 + `im:chat` 权限 | ❌ 一直是死的，已删 |

也就是说**"告警从来没送达"要收窄成"飞书那条腿从来没送达"**——弹窗用户其实一直看得见，
少的是事后可查的凭据。这是本次退役补上的东西。

两棵部署树都还停在旧提交（`finance-workspace-private` 落后 428 提交且工作树脏、
`finance-workspace-runtime` 落后 83 提交），所以 `notify_ops.py` 在它们那里还不存在，
落盘那条腿要等它们更新。**更新部署树属于部署动作，没有擅自做。**

另：`notify_ops.py` 本身也会弹窗，而 shell 已经内联弹过一次 → 检出更新后会同一件事响两声。
已加 `--no-desktop`（shell 调用处传它，只落盘），并补上该脚本的 7 条测试（前身 `notify_feishu.py` 一条测试都没有，
这正是它每晚 400 却没人发现的原因）。

## 剩你一步（我不碰你的账号）

到**飞书开放平台 → 开发者后台 → 找到那个自建应用（app_id 在 `~/.finance-runtime/retired-feishu-20260911/feishu_config.json.bak` 里，本文不抄）→ 删除应用**。

为什么这一步不能省：那把 `app_secret` 曾以明文进过 git 历史（`26446460`，2026-07-02 只从工作树删），
**历史里至今仍在，且 09-11 实测仍然有效**。删掉应用等于让那串明文当场作废——这是唯一能真正关门的动作。
删完后可以把 `~/.claude/shared/`（只剩 `feishu_config.json` + `feishu_utils.py`）和仓内 `shared` 软链一起清掉。

## 验证

- 全量 `pytest`：**9151 passed / 77 skipped / 1 xfailed**（344s）
- `ruff check .`：干净
- `build_registry` 注册表与工作树 skill 集合一致（33 个）自证通过
