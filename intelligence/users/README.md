# 用户应用态命名空间 `intelligence/users/<user_id>/`

把**因人而异**的状态（画像 / 记忆 / 反馈 / 策略 overlay）从共享代码与共享市场数据里
剥离出来，按用户收口。现在只有一个用户也能照常跑（`default`），以后服务多个用户时只要
传一个新的 `--user <id>`（或设 `FORESIGHT_USER` 环境变量）即可隔离其全部状态。

`user_id` 约束：字母/数字开头，仅允许 `A-Za-z0-9._-`，长度 ≤ 64；杜绝路径穿越
（解析逻辑见 `intelligence/userspace.py`）。

## 每个用户目录里的文件

| 文件 | 谁写 | 入库? | 说明 |
| --- | --- | --- | --- |
| `profile.json` | 人（钉住） | 否 | 用户钉住的画像，优先级最高，`refresh-profile` 不会覆盖它 |
| `profile.derived.json` | `refresh-profile --apply` | 否 | 自动派生候选，带 `source`/`as_of`/`stale` 标记 |
| `foresight_memory.jsonl` | `foresight` | 否 | 问过的问题记忆回路（去重用） |
| `interactions.jsonl` | `record-interaction` | 否 | 点击/追问/喜欢/忽略/打分反馈，用于「越用越懂」 |
| `corrections.jsonl` | `record-correction` | 否 | 你纠正它的高信号记录，注入发问「别再犯」（纠偏回路） |
| `judgments.jsonl` | `subconscious commit` | 否 | 深挖纪要沉淀的核心判断台账，注入发问「在此基础上往前推」 |
| `strategy_params.json` | 人 | 否 | 个人策略参数 overlay（稀疏覆盖共享 baseline） |

以上**运行时文件全部 gitignore，不入库**（含真实自选股、提问历史等隐私）。仓库里只跟踪
本 README、`profile.template.json` 与 `strategy_params.template.json` 模板。

## 跨机同步：`FORESIGHT_USERS_DIR`（两机一个大脑）

上面这些文件默认落在仓库内 `intelligence/users/<id>/`，`git pull` **不会**带过去（已 gitignore）。
要让多台机器共享同一个大脑，设环境变量 `FORESIGHT_USERS_DIR` 把整个 `users/<id>/` 目录
重定位到云同步盘（支持 `~` 展开）；所有读写（`foresight` 亲和度、`record-interaction`、
`refresh-profile`、潜意识模式）都经 `userspace.user_space()` 解析，自动跟随，无需逐处改。

```bash
# 两台机器都这样配；指向 Obsidian 沉淀 vault 内的隐藏目录，随 vault 云同步
export FORESIGHT_USER=<id>
export FORESIGHT_USERS_DIR="$HOME/路径/到/沉淀vault/.foresight"
```

不设则保持原样（仓库内、单机）。`.` 开头目录 Obsidian 默认不显示，不会污染 vault 视图。

## 越用越懂：反馈回路 `interactions.jsonl`

每条「猜你想问」问题被点开 / 追问 / 喜欢 / 忽略 / 打分时记一笔，下次 `foresight` 排序就会
对相关题材/个股给一项**可解释**加成（近期正向互动升权、被忽略/打低分降权，带时间衰减）。

```bash
# 点开了一条关于「液冷」的问题（kind 默认权重见 intelligence/services/interactions.py）
python3 -m intelligence.cli record-interaction --user <id> --kind click \
    --theme 液冷 --stock 中际旭创 --question "液冷渗透率拐点何时到？"

# 不感兴趣 → 降权
python3 -m intelligence.cli record-interaction --user <id> --kind dismiss --theme 钠电

# 1~5 星打分（映射到 [-1,1]）
python3 -m intelligence.cli record-interaction --user <id> --kind rate --rating 5 --theme 算力
```

常用 `--kind`：`click/open/ask/like/follow/pin`（正向）、`view/impression`（弱正向）、
`skip/ignore/dismiss/mute/dislike`（负向）、`rate`（配 `--rating`）。`--weight` 可显式覆盖。
foresight 默认开启加成，`--no-interactions` 关闭、`--affinity-boost 0` 等价关闭、
`--affinity-half-life` 调时间衰减半衰期（天）。

## 懂你的复盘思路：思考宪法 + 纠偏回路（不靠点击猜偏好）

foresight 发问前会注入两样东西，让它**在你的复盘框架里推理**，而不是用通用脑子发泛泛的问题：

1. **思考宪法**：`intelligence/foresight_methodology.md`（入库、可编辑）。提炼自你的复盘规则、
   知识库证据分层与各输出模块（策略生成 / 卖方观点提纯 / 机构胜率 / 晨汇边际变化 / 题材发酵）
   的「7 条元思路」。你随时改这个文件就改了它发问的脑子，**无需动代码**。
2. **纠偏回路**：`users/<id>/corrections.jsonl`（gitignore）。你不满意它的回答时纠正一笔，
   下次发问自动带上「别再犯同类错误」。这条**不靠点击猜你喜欢哪个题材**（深挖≠偏好、市场动态），
   只靠你的**显式纠正**学方法论。
3. **核心判断台账**：`users/<id>/judgments.jsonl`（gitignore）。潜意识模式 `commit` 时把你深挖
   纪要里的「核心判断」同步落进这本机器可读台账（不只进 Obsidian），下次发问注入最近 N 条，
   让新追问**站在你旧判断上往前推一层或找它的反例**，而不是每轮从零重述你已想清楚的东西。

```bash
# 它答错了 → 记一条纠偏（correction 必填；principle 抽象出可复用原则，最该被记住）
python3 -m intelligence.cli record-correction --user <id> \
    --correction "先判断板块走到哪一阶、强到哪一档再下结论，不要会/不会二元定论" \
    --original "氟化工要爆发了" \
    --principle "分级不二元" --theme 氟化工
```

foresight 默认三者都注入：`--no-methodology` 关闭思考宪法、`--no-corrections` 关闭纠偏、
`--no-judgments` 关闭近期核心判断、`--corrections-window N` / `--judgments-window N` 只带最近 N 条、
`--methodology-file` / `--corrections-file` / `--judgments-file` 改路径。渲染头部会显示
「方法论：注入思考宪法 N 字 · 带 M 条纠偏」与「旧判断：承接 K 条核心判断往前推」，方便确认生效。

## 按用户的策略迭代：`strategy_params.json`（稀疏 overlay）

`evolution/params.json` 是所有用户共享的 baseline；`strategy_params.json` 只写想覆盖的
策略段（`strategy1` / `strategy3` / `strategy4` / `validation` / `suggest`），自带
`_overlay_version`。evolve 加载时把 overlay **深合并**到 baseline，输出落到
`evolution/users/<id>/{records,validation,suggestions,进化.md}`（与共享 baseline 输出隔离，
互不覆盖），记录里留痕 `user` + `params_overlay_version` + `params_overlay_sections`。

```bash
cp intelligence/users/strategy_params.template.json \
   intelligence/users/<id>/strategy_params.json   # 编辑只留想改的段

cd <repo root>
PYTHONPATH="$(pwd)" python3 scripts/evolve.py generate --user <id> --date 2026-06-13
PYTHONPATH="$(pwd)" python3 scripts/evolve.py validate --user <id> --strategy 1
PYTHONPATH="$(pwd)" python3 scripts/evolve.py audit    --user <id>
```

确定性不变：同一 baseline + 同一 overlay + 同一 DB → 100% 可复现；不传 `--user` 就完全
等价于历史共享 baseline 行为。

## 生效画像 = 钉住 ⊕ 派生

`foresight` 取的「生效画像」由 `userspace.effective_profile()` 合并得到：
`profile.json`（钉住项在前）⊕ `profile.derived.json`（未过期派生项补充、去重）。
派生项连续多次未被 `refresh-profile` 命中会先标 `stale`（停止影响 foresight），再彻底删除。

## 新增一个用户

```bash
mkdir -p intelligence/users/<user_id>
cp intelligence/users/profile.template.json intelligence/users/<user_id>/profile.json
# 编辑该 profile.json，钉住该用户的 name/style/horizon/focus_themes/watchlist

# 让系统自动从 DuckDB 强势股 + 知识库 theme_signals 派生候选（默认只预览 diff）
python3 -m intelligence.cli refresh-profile --user <user_id>
python3 -m intelligence.cli refresh-profile --user <user_id> --apply   # 确认后落盘

# 用该用户跑「猜你想问」
python3 -m intelligence.cli foresight --user <user_id>
```

## 向后兼容（default 用户）

`default` 用户沿用历史文件位置以保证零迁移、提问记忆不断档：

- 画像：`intelligence/foresight_profile.local.json`（私有，gitignore）→
  `intelligence/foresight_profile.example.json`（仓库默认）
- 记忆：`intelligence/foresight_memory.jsonl`

显式 `--profile <file>` / `--memory-file <file>` 仍然优先于用户命名空间解析。
