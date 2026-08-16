# 2026-08-16 sptfei 视角数据迁移交接（linxiaoqi5111 → default）

roadmap_ref: 另案（perspective-lab 无 L1 战役；纯数据面操作，不动代码、不动 8792 服务、不碰 git）

一句话：SPT-Molmansk（`sptfei`，4 篇文章）在 canonical 数据根的 `linxiaoqi5111` 名下，而 workbench UI 的默认身份是 `default`，所以页面上看不到；且 manifest 里的 `raw_path` 还指向已废弃的旧根，就算切身份检索也是空的。迁移 = 拷三处目录 + 改写 manifest 路径 + 验证。

证据等级：**[实测]** = 2026-08-16 跑过命令/读过代码。

## 1. 为什么会这样（两根两身份的历史）

- **身份错位** [实测]：workbench 启动器（`~/.local/bin/start-finance-workbench`）设了 `FORESIGHT_USERS_DIR=/Users/a77/.local/share/finance-workbench/users`，没设 `FORESIGHT_USER` → UI 默认身份 `default`。`/api/perspectives`（不带 user 参数）只返回 `default` 名下的 fengyuan（0 篇）。
- **根错位** [实测]：`sptfei` 是 2026-08-13 15:15 一次 agent/CLI 会话 ingest 的，当时 users 根是 `~/agent-memory/.foresight`（「两机一个大脑」同步盘设计），身份用 `linxiaoqi5111`。manifest 的 `raw_path` 至今指向 `/Users/a77/agent-memory/.foresight/linxiaoqi5111/perspectives/articles/sptfei/raw/*.md`。
- **收敛不彻底** [实测]：canonical 数据根收敛时目录被原样拷进 `~/.local/share/finance-workbench/users/linxiaoqi5111/`（mtime 保留 08-13 15:15），但身份没并、manifest 绝对路径没改写。
- **旧路径检索空转** [实测]：`perspective_lab.py:386-392`（快照 437cd5e9）读文章时有越界防护——`raw_path` 必须落在**当前 UserSpace 的 perspectives 根**内，否则静默 `continue`。现状下 `linxiaoqi5111` 名下 4 条记录全部指向根外 → BM25 片段检索 0 文档。`article_count=4` 能显示是因为列表 API 只数 manifest 行数，和检索是两条路。

## 2. 迁移步骤（用户或 agent 皆可执行，无 git 红线）

```bash
SRC=/Users/a77/.local/share/finance-workbench/users/linxiaoqi5111/perspectives
DST=/Users/a77/.local/share/finance-workbench/users/default/perspectives
mkdir -p "$DST/profiles" "$DST/articles" "$DST/patches"
cp -p  "$SRC/profiles/sptfei.json" "$DST/profiles/"
cp -Rp "$SRC/articles/sptfei"      "$DST/articles/"
cp -Rp "$SRC/patches/sptfei"       "$DST/patches/" 2>/dev/null || true

# 改写 manifest 的 raw_path 到新位置（关键一步，漏了检索仍是 0）
python3 - <<'PY'
import json, pathlib
m = pathlib.Path('/Users/a77/.local/share/finance-workbench/users/default/perspectives/articles/sptfei/manifest.jsonl')
raw_dir = m.parent / 'raw'
out = []
for line in m.read_text(encoding='utf-8').splitlines():
    if not line.strip():
        continue
    rec = json.loads(line)
    rec['raw_path'] = str(raw_dir / pathlib.Path(rec['raw_path']).name)
    out.append(json.dumps(rec, ensure_ascii=False))
m.write_text('\n'.join(out) + '\n', encoding='utf-8')
print('rewrote', len(out), 'records')
PY
```

不需要重启服务：`list_perspectives` 和 `_article_documents` 每次请求现读磁盘，无缓存 [实测：读代码确认]。

## 3. 验证

```bash
# 1) 列表：default 名下应出现 sptfei，article_count=4
curl -s 'http://127.0.0.1:8792/api/perspectives' | python3 -m json.tool --no-ensure-ascii

# 2) 检索冒烟：BM25 能召回片段（>0 条）
cd /Users/a77/finance-workspace-runtime && \
FORESIGHT_USERS_DIR=/Users/a77/.local/share/finance-workbench/users \
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -c "
from intelligence import userspace
from intelligence.services import perspective_lab as pl
us = userspace.user_space('default')
hits = pl.retrieve_article_snippets(us, 'sptfei', '跨年 综述 市场')
print('snippets:', len(hits))
assert hits, 'BM25 召回为 0，检查 manifest raw_path 是否改写成功'
"

# 3) UI：刷新 workbench，视角选择器里应看到 SPT-Molmansk（4 篇 / medium）
```

## 4. 验证通过后的可选清理（避免双份漂移）

- 删 `~/.local/share/finance-workbench/users/linxiaoqi5111/perspectives/{profiles/sptfei.json,articles/sptfei,patches/sptfei}`——这份是收敛时的坏拷贝（路径指根外），留着只会误导下次排查。
- **不动** `~/agent-memory/.foresight/` 原件：那是 agent 线的历史原始数据，且在同步盘语义下删除会传播到另一台机器。

**[已执行 2026-08-16]** 坏拷贝已删；`.foresight` 原件 4 篇仍在。删后 `/api/perspectives` 仍是 sptfei×4，BM25 仍召回 3 条。

## 5. 防复发

以后要让视角在 workbench 页面可见，ingest 必须同时对齐根和身份：

```bash
FORESIGHT_USERS_DIR=/Users/a77/.local/share/finance-workbench/users \
python3 -m intelligence.cli perspective ingest --user default \
  --perspective sptfei --input <文章.md> --title <标题> --date <YYYY-MM-DD> --source weixin-sptfei
```

根本性的收口（要不要把 agent 会话的 users 根统一指到 canonical 根、退役 `.foresight`）是另一个决定，不在本交接范围。

**[已执行 2026-08-16，未改共享大脑根]** 复发口实测是三处同时指旧根旧身份，不能只改一处：

- `~/.zshrc`：`FORESIGHT_USER=linxiaoqi5111` + `FORESIGHT_USERS_DIR=~/agent-memory/.foresight`（只加了注释，**没改 export**——改根会拆掉 corrections/checkpoints/夜间回检）。
- `skills/daily-full-review/scripts/nightly_full_review.sh` 与 launchd `com.financeworkspace.checkpoint-recheck` 同样指向 `.foresight` + `linxiaoqi5111`。
- `skills/perspective-distill/SKILL.md` 第 0 步路径对了，但 user 写成「本机生产是 `linxiaoqi5111`，不是 `default`」——launcher **不设** `FORESIGHT_USER`，UI 实际是 `default`。已改正，并加 `~/.local/bin/perspective-workbench`（从 launcher 读根，默认 `--user default`）。

以后页面可见的 ingest：

```bash
perspective-workbench ingest --perspective sptfei --input <文章.md> --title <标题> --date <YYYY-MM-DD> --source weixin-sptfei
```

## 6. 顺带：fengyuan（风远）

**[纠偏 2026-08-16]** 前一版把 `article_count=0` 读成「空画像 / 可删占位」是错的。

分两层：

| 层 | 状态 | 在哪 |
|---|---|---|
| 认知框架 | **有** | `kol_fengyuan` 种子（`perspective_lab.py`）+ `default/perspectives/profiles/fengyuan.json`（2026-07-17 写入：双锚 / 出清形态 / 五维排序 / 三级信号 / 供给侧通胀）+ 蒸馏笔记 `docs/learning/knevo-distill/`（q1/q2 等，来源标注「风远94共享数据库」） |
| 原文仓 / BM25 | **空** | `articles/fengyuan/raw` 无文件、无 manifest；检索 0 条。IMA 也没有名叫「风远」的库（本机只有长安投研 / 浑水调研 / gray） |

`type=kol_fengyuan` 不是 `blogger`，`low_sample` 闸不套它——选中后镜头仍进 prompt。

**不要删** `default` 下的 fengyuan。也不要把 `knevo-distill/` 当原文 ingest（那是我方蒸馏笔记，不是风远原文）。

## 7. 残留缝已修（本分支）

`_profile_prompt` 原先在无 snippet 时一律写「该视角未知」，会把种子画像的 5 个镜头冲掉。现改为：画像已有认知框架时，只声明「未召回相关文章，本轮用画像框架作镜头」；空 blogger 仍写未知。契约句「原文未覆盖的问题必须写该视角未知」保留。

代码在 `fix/seeded-perspective-unknown`（Gitea PR **#76** `http://127.0.0.1:3300/a77/finance-workspace-private/pulls/76`），**尚未切进 8792 runtime**（快照仍是 `437cd5e9`）。要线上生效需合入后再部署，不在本数据迁移里重启。
