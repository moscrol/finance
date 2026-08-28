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
- 绿灯：经验卡+召回+auth+quota 定向测绿（执行方写 50；检阅方重跑同四文件 **62 passed**，收据 dirty）
- 纠偏：仓内 27→23；生产 116→112；留下的 3 条 ts 仍在（生产没有「结构化腔」那条，属预期）

## 不要做

- 不要在 8792 上 `WORKBENCH_AUTH_MODE=cf_access` 除非向导跑完且 AUD/名单齐。
- 不要 `cloudflared tunnel create` 第二条。
- 不要把实验 `eval/runs/` 和探针目录当产品代码提交。
- 不要把 4/6/7 三条纠偏当「已在管线」归档。

### 检阅批注 · 2026-08-28 16:15（独立质检，未合、未切）

- **判定**：产品主张 **PASS**。合入门 **未就绪**（不是产品打回）。
- 独立复核：
  - `load_cards` 与 `invalidated` 同 choke；仓内 16 行 → `window=0` 返回 0。
  - CLI `--promotion` 含 `promoted_to_code`。两条产品 load（`ask.py` / `ask_synthesis.py`）都先走 `load_cards`。
  - 纠偏只追加 4 条 `memory_status`；仓内 27→23、生产 116→112。留下 4/6/7 的 ts 仍 live。
  - 8792 health：`e5d45933` / `auth_mode=off` / 生产目录无 `experience_cards.jsonl`。启动器无 `WORKBENCH_AUTH_MODE`。向导 `bash -n` 过，`alpha.env` 不存在。
  - 定向 pytest 62P / 0F，收据 `20260828T080133Z-b6648f60.json`，**`dirty=True` dirty_total=41**（他人复盘/实验文件）。exit 0 对脏树成立，不对干净 revision 成立。
  - `graph_audit`：43 行 / 49 条，exit 0（本仓树 dirty 已声明）。
  - `git merge-tree gitea/main HEAD` **rc=1**：`docs/prediction-ledger.md` 头行冲突。独有提交 3 个：`e4276e00`（账本头，不在 `gitea/main`）+ 本枝两记。left-right `78/3`，merge-base `fea0633e`。本枝产品文件与账本冲突正交——合入前 rebase 到 `gitea/main`，丢掉或重做 `e4276e00` 头行。
  - 无远端分支、无 PR。
- 标注：
  - 第三份脑 `~/agent-memory/.foresight/linxiaoqi5111`：14 张卡仍 methodology/promoted（`load_cards`=14），纠偏 72 条 0 归档。当前 8792/本壳 env 不指那里。
  - 「留下 3 条」≠ 常驻 5：常驻窗是最近 5 条带原则的，现被 7 月底运营纠偏占满；4/6/7 只走相关记忆。
  - 第 7 条「完全没有等价点」过满：复盘题编排合同已有「只用用户语言」。不是硬闸，留下仍对。
  - 第 4 条更该留：`theme_lifecycle` 把「澄清」放进证伪词表，方向相反。
- 未代做：独立 worktree 干净复跑、合入、切 8792、跑向导。
