# 换手率不是采不到，是采回来被丢了

> 日期：2026-09-06
> 分支：`fix/eastmoney-turnover-f8`（从 `gitea/main` 独立开树，**不依赖** river 那四张栈式 PR）
> 起因：数据代码化审计报「`fact_stock_daily.turnover` 全库非空 0 行」，我一度对外说成「算不出来 / 采不到」。
> 状态：**未合并**。

## 0. 结论

**`turnover` 一直在被请求、数据一直在回来，只是解析时被硬绑成 `None`。**
东财快照的请求字段表里写着 `f8=换手率%`，但全文件没有一处 `it.get("f8")`。

改法一行。修完东财那条路径（当前 237,818 行、且是日常单日复盘的默认源）往后立刻有值；
mootdx 那 1,804,922 行仍是 NULL——**那是来源差异，不是缺陷**，已写进模块 docstring。

## 1. 怎么定位到的

审计只能告诉你「这列是 0」。判成哪一种病必须逐个看写入方。用的判据是**兄弟列填充率**：
同一张表、同一个写入方、同一种取值写法，如果兄弟列填满而它是 0，那问题就不在管线在字段。

| 列 | 兄弟列 | 判定 |
|---|---|---|
| `fact_stock_daily.turnover` | — | 三个写入方都写了「留空」注释 → 看请求字段表 → **f8 请求了没接** |
| `fact_market_daily.sh_index_amount` | `sh_index_volume` 99.3%、`close` 99.8%，**同一个 `_pick(raw, "amount", "成交额")`** | 上游那个键不在返回里 → 采不到 |
| `fact_sector_daily.strength` | — | 写入方绑定元组第 8 位是**字面量 `None`**，从没去 payload 取；`ON CONFLICT` 里也漏了它 |
| `fact_theme_limit_stock_daily.open_times` | `first_limit_time`/`last_limit_time` 99.9% | 接口不给 |
| `fact_sector_stock_daily.free_float_mcap_yi` | `circ_mv` 98.8%、`float_mcap_yi` 96.2% | 接口不给 |
| `fact_sector_stock_daily.leader_sub_plate` | 同名键在 `fact_theme_limit_stock_daily` 里 **49.9%** | 这个接口没有、另一个有 |
| `fact_mainline_sector_daily.startup_date_extend` | small 60% → big 1.3% → super 0.1% → extend 0% | **梯度，像事件稀有度，可能根本不是缺陷** |

**「填充率 0」不是一种病，是四种**：采回来丢了 / 写漏了 / 接口不给 / 事件没发生过。
处置完全不同，其中一种**不该动**。

## 2. 改了什么

| 文件 | 改动 |
|---|---|
| `market_feature_store/sync/sync_eastmoney_stock_snapshot.py` | `turnover = _num(it.get("f8"))` 并绑进写入行；docstring 写明 mootdx 行仍为 NULL 是来源差异；`EM_FIELDS` 去掉 `f13` |
| `tests/test_eastmoney_snapshot_fields.py` | 新增 6 条 |

### 为什么顺手去掉了 `f13`

写完门禁第一次跑，它当场又抓到**第二个被丢的字段**：`f13`（市场标识）也请求了从不读。

但**不能改用 f13 派生交易所后缀**：`_ts_code` 是与 mootdx **共用**的前缀派生
（6→SH / 0,3→SZ / 其余→BJ）。东财改用 f13 而 mootdx 不改，同一只股票会在两个来源下拿到
不同的 `stock_ts_code`，在同一张表里裂成两个实体。所以正解是**不请求它**，不是改派生。
全树确认无别处依赖 `f13` / `EM_FIELDS`。

## 3. 门禁：请求了就必须接

只钉 turnover 挡不住下一次——换个字段还会同样丢。所以钉的是通用规则：

```python
unread = [f for f in EM_FIELDS.split(",") if f'it.get("{f}")' not in src]
assert unread == []
```

要么接住它、要么从 `EM_FIELDS` 里去掉，**不许请求了扔掉**——那会让审计侧看成「上游采不到」，
把一个一行能修的问题伪装成一个换数据源的工单。这正是本次的事故形状。

## 4. 测试与变异

6 条：请求字段全被消费（门禁）、f8 已声明、**端到端 f8=3.42 落到写入行的 turnover 列**、
来源给 `None`/`"-"` 时保持 NULL 不填 0、**真的 0% 换手率要存成 0**（不能被「假值当空值」吞掉）、
旧的硬绑 `None` 不许回来。

端到端那条只桩掉「连库」与「发请求」，**解析与装行的代码原样跑**——桩到解析层就是自己跟自己
对答案，测不出「f8 被丢掉」这种事。

| 变异 | 实测 |
|---|---|
| 往 `EM_FIELDS` 加一个没人读的 `f20` | 1 红（门禁生效） |
| 把 `turnover` 绑回 `None` | 3 红 |

## 5. 全量

见 §6。

## 6. 全量读数

干净 worktree（从 `gitea/main` 开、无 `db/`，即本仓分支门禁的惯例环境），同一隔离壳：

```
1 failed, 7739 passed, 15 skipped, 1 xfailed in 365.62s
```

唯一那条红是 `test_installed_codex_sandbox_denies_network_and_unix_socket`——sandbox 环境项，
今天每一轮（主树、基线树、本树）都红，与本刀零交集。

**顺带印证了同日另一线的归因**：主树上那另外三条红在本树**全部不出现**——
`test_conversation_orchestrator` 需要真库（本树无 `db/`）、`test_double_red_single_source`
点名的是 river 分支的 `river_window.py`（本树基于 main，没有那个文件）、
`test_code_map` 需要预建 graph.db（本树无）。三条各有各的环境依赖，都不是代码回归。

`ruff check`：All checks passed。

## 7. 没做 / 边界

- **不回填历史**。历史行的换手率没存过，现在也补不回来——除非重新拉东财历史快照（另一单）。
  这条改动只保证**往后**每天都有。
- **mootdx 路径仍无换手率**，1,804,922 行保持 NULL。消费方按 NULL 处理，不要拿 0 顶替：
  0% 换手率是有含义的读数（停牌）。
- **另外六列没动**。`strength` 需要先确认 fupanhui K 线接口给不给这个键（要 CDP 登录态）；
  三个「接口不给」的属于换数据源，单独立单；`startup_date_extend` 要先确认语义，
  如果真是「超大级别启动日」，0 行就是正确读数，**不该改**。
