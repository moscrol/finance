# 2026-08-28 · 经验卡 promoted_to_code 与 Alpha 向导

## 背景

上一轮 UMD 三臂实验证伪「把方法论做成数据库附带」：冷启动零注入，答案仍带全套方法论骨架。骨架来自 `answer_orchestrator` / stock-deep-dive 十二视角 / `answer_lint`。用户确认裁决后要求执行：标卡 + 发 alpha。

展开：`docs/superpowers/specs/2026-08-28-shared-memory-plane-design.md` §7，计划 `docs/superpowers/plans/2026-08-28-promoted-to-code.md`。

## 发现顺序

1. 仓内 `linxiaoqi5111/experience_cards.jsonl` 有 16 行：3 invalidated + 13 live（6 methodology / 6 promoted / 1 candidate）。
2. 生产 8792 的 `FORESIGHT_USERS_DIR` **没有** experience_cards.jsonl——生产本来就不注入这 13 张。CLI 默认路径才会。
3. 纠偏两边都有。`select_resident_principles` 会把带 principle 的最近 5 条常驻注入。
4. 「澄清≠证伪」在代码里搜不到等价强制点；相对日期解析只吃显式日期，不把「今天」绑到已给的复盘截止日；「结构化腔」在 intelligence 里搜不到。
5. Hosted Alpha 认证代码已在 main（`auth.py` / `quota.py`），但启动器无 `WORKBENCH_AUTH_MODE`，cloudflared 在跑别的主机名。翻 `cf_access` 而 CF Access 没配好 = 8792 起不来。

## 决策对比

| 问题 | 选 | 否 | 为什么 |
|---|---|---|---|
| 退役怎么表达 | `promotion=promoted_to_code`，`load_cards` 跳过 | `invalidated=True`；删行；shared JSONL 层 | 这些卡是对的；删行破坏回放；shared 层已被实验否掉 |
| 过滤落点 | 只 `load_cards` | 再在 select_resident/relevant 滤一层 | 唯一注入口；散滤会漂 |
| 飞凯 candidate | 一并退役 | 留下当个股笔记 | 原则「事实层交叉验证叙事层」已在管线；卡不当事实引用 |
| 7 条纠偏 | 只归档 1/2/3/5 | 7 条全归档 | 4/6/7 还没进代码，归档会丢真差异化 |
| Alpha | 向导写 alpha.env，不改启动器 | 现在就 source + kickstart | 缺 AUD 启动即抛 |

## 验证

- 红灯先行：`load_cards` 仍返回 Q2 / 召回含 e4
- 绿灯：经验卡+召回+auth+quota 50 passed；`graph_audit` OK；真实文件 `load_cards` 0 张
- 纠偏：仓内 27→23；生产 116→112；留下的 3 条 ts 仍在（生产没有「结构化腔」那条，属预期）

## 不要做

- 不要在 8792 上 `WORKBENCH_AUTH_MODE=cf_access` 除非向导跑完且 AUD/名单齐。
- 不要 `cloudflared tunnel create` 第二条。
- 不要把实验 `eval/runs/` 和探针目录当产品代码提交。
- 不要把 4/6/7 三条纠偏当「已在管线」归档。
