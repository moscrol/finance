# 恢复被 #727 连带删除的 5 个 skill（#729）

- 分支：`restore/feishu-skills`，基于 `21f9eb9c`（#727 合并后的 main）
- 触发：用户裁定「那几个 skill 别删，skill 只是写入飞书的，他们是有用的」
- 关联：#727「飞书整体退役」、`docs/handoffs/inflight/chore-retire-feishu.md`

## 一、#727 删了什么

飞书基础设施（**本次不恢复，用户未反对这部分**）：
`scripts/notify_feishu.py`、`intelligence/chat/feishu_bot.py`(+plist+test)、
`market_feature_store/sync/sync_feishu_{market_daily,sector_daily,sector_marginal,sector_resonance,limit_advance}.py`。

连带删掉的 **skill 本体**（本次恢复）：

| skill | #727 处置 | 本次 |
|---|---|---|
| advancers-chart | 整目录删（4 文件） | 全恢复 |
| up-line | 整目录删（3 文件） | 全恢复 |
| watchlist-ma | 整目录删（2 文件） | 全恢复 |
| sector-data | 整目录删（2 文件） | 全恢复 |
| top-gainers-feishu | 整目录删（4 文件） | 全恢复 |
| market-overview | 挖空 3 个脚本/参考 | 恢复 3 个 |
| limit-advance | 挖空 3 个脚本 | 恢复 3 个 |
| high-volume-gainers | 挖空 `write.py` | 恢复 |

另恢复：`.claude/skills/` 下 4 个 agent 视图软链、`tests/test_limit_advance_write.py`、
`skills.registry.json` 5 条（ws 计数 33→38）、`CLAUDE.md` 生成块 5 行（表块已与删前逐字节一致）。

## 二、核实到的前提偏差（重要）

用户的判断是「skill 只是写入飞书的」。逐个查过 `import`/调用点后，**5 个里有 4 个的输入也来自飞书表**：

| skill | 输入 | 输出 | 现在跑得通吗 |
|---|---|---|---|
| up-line | 飞书三张表（`fetch_all_records`×4）+ iFinD×6 | 写飞书 | ✗ 输入与行情都没了 |
| watchlist-ma | 飞书自选股表 + iFinD | 只读展示 | ✗ 同上 |
| top-gainers-feishu | 飞书强势股表 + iFinD×7 | 写飞书 | ✗ 同上 |
| advancers-chart | 飞书表（`fetch_all_records`×3） | 图表 + 写飞书 | ✗ 无本地输入 |
| sector-data | **fupanhui（独立）** | 写飞书 | 取数可用，写入失效 |

所以恢复保住的是**口径与逻辑**（UP = MA26 + 0.764×STD26、均线回踩判据、加权涨幅口径、
涨家数取数），不是「立刻可跑的链路」。要真正复活前 4 个，需把清单与行情改接 DuckDB
（`fact_stock_daily` / `market_feature_store.cli`）——**这是一件独立的活，待裁定**。

`shared/feishu_utils.py` 仍在（`~/.claude/shared`，gitignore 之外，#727 动不到），
所以恢复的脚本在 import 层面不破；断的是凭证与飞书应用本身。

## 三、与 #727 门禁的冲突及处理

#727 新增 `tests/test_pipeline_p0.py::test_no_module_reads_feishu_credentials`，
断言仓内不得再有任何文件引用 `feishu_utils` / `feishu_config.json` / `tenant_access_token`
/ `FEISHU_APP_SECRET`。恢复 skill 会命中 14 处 → 直接红。

实测这 14 处**全部落在 `skills/`，自动链路（`market_feature_store/` `intelligence/` `scripts/`）零命中**。
门禁自述的目的是「用户在开放平台上删掉应用就会把某条链路打断」——`skills/` 下是人/agent
显式触发、且已无任何流水线调用（#727 已把 advancers-chart 从 daily-full 链上摘掉），
删应用不会打断任何链路。故把门禁**收窄**而非放行：

- 活链路：**绝对禁**，原样保留（断言文案改为「自动链路不得重新引入」）。
- `skills/`：**逐文件钉死的封存名单**（13 条），新增读取点仍然红——只保留不扩张。

双向变异验证：
- 在 `skills/up-line/scripts/` 放一个新的 `from feishu_utils import ...` → 红（「封存名单只保留不扩张」）。
- 在 `market_feature_store/` 放一个 `import feishu_utils` → 红（「自动链路不得重新引入」）。
- 都撤掉 → `tests/test_pipeline_p0.py` 28 passed。

## 四、文档口径修正

#727 的行文写的是「脚本已不存在 / 已删除」，恢复后这些话成了假话，逐处改成
「写入步骤因凭证退役而失效，脚本保留在仓内（见 #729）」：
`market-overview/SKILL.md` 4 处、`high-volume-gainers/SKILL.md` 1 处、`limit-advance/SKILL.md` 1 处、
`dispatcher/SKILL.md` 恢复 5 行可发现性表行（写入步已停的标注 `✅ xxx.py（写入步已停）`）。

5 个恢复的 SKILL.md 各加一条横幅，写明**它自己**的输入/输出/是否跑得通与复活路径。

## 五、遗留

- `skills.registry.json` 里 `ws/handoff`、`ws/perspective-distill` 两条与仓内 SKILL.md 不一致，
  是 main 既有漂移，与本次无关，未擅自改。
- 恢复的 SKILL.md 里仍有历史遗留的绝对路径 `/Users/lbq/Desktop/c c/金融/...`（删前就在），本次未动。
- 前 4 个 skill 改接 DuckDB 才能真正复活，待用户裁定是否要做。
