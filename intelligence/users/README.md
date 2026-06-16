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
| `interactions.jsonl` | （PR2）反馈回路 | 否 | 点击/采纳/忽略反馈，用于「越用越懂」 |
| `strategy_params.json` | （PR2）人/evolve | 否 | 个人策略参数 overlay（稀疏覆盖共享 baseline） |

以上**运行时文件全部 gitignore，不入库**（含真实自选股、提问历史等隐私）。仓库里只跟踪
本 README 与 `profile.template.json` 模板。

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
