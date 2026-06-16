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
| `strategy_params.json` | 人 | 否 | 个人策略参数 overlay（稀疏覆盖共享 baseline） |

以上**运行时文件全部 gitignore，不入库**（含真实自选股、提问历史等隐私）。仓库里只跟踪
本 README、`profile.template.json` 与 `strategy_params.template.json` 模板。

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
