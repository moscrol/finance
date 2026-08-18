# 验收工作流（QC session 规程）

> 场景：执行方交付了一批 PR + handoff，新 session 独立验收 → 合并 → 批次门禁 → 切 8792 → 回写台账。
> 出处：2026-08-18 九张批次实战定形（#167 先决单 + KC 七张 + #120 superseded）；当时读数见台账 10:50 / 11:05 两行。

## 0. 拉齐队列

读 `docs/handoffs/inflight/main.md` 顶部拿队列与起点。每张 PR 的验收基准 = 对应 handoff 的「验收标准」节；PR 描述是执行方自述，只作导览。

排序：**先决单**先走——改路径 / 环境 / 数据根解析的单在前，其余单的 live 判据依赖它落地。

**完成判据**：能对队列里每张 PR 说出「验收标准在哪个文件哪一节」。

## 1. 环境

- 解释器只用 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`（宿主 python3 无依赖）。
- 测试壳：`env -i PATH="$PATH" HOME="$HOME" KNOWLEDGE_WIKI="$KNOWLEDGE_WIKI"` + `umask 022`。继承 launcher 变量 → 31 假红；umask 077 → 16 假红（2026-08-18 台账 02:25 行⑤实测）。
- 每批用独立 worktree 验；`/Users/a77/fwp-wt-167-merge` 是现成验收树（webapp node_modules 已装）。
- Gitea API token 在 Keychain：`security find-generic-password -s gitea-local -a a77-token -w`。scope 最小集 `write:issue,write:repository,write:user`（2026-08-18 已补；缺 `write:issue` 时评论 403）。

**完成判据**：pytest 收据（`~/.finance-runtime/test-receipts/<ts>-<treesha>.json`）文件名里的树 SHA == 你正在验的树。

## 2. 逐张验收

0. **别信 Gitea 的 `mergeable`**（2026-08-18 实测补入）：#178–#194 十张全报 `mergeable=true`，实际 #190/#194 有真冲突，与 patch-checker 队列故障同源。自己探：
   `git merge-tree --write-tree gitea/main <branch>`，exit 0 = 干净，非 0 时输出里有 `CONFLICT` 行。
   另外先确认队列是不是**堆叠链**：`git rev-list --left-right --count <前一张>...<后一张>`，左侧为 0 = 后者含前者，此时链内不能改序、也不能单独打回中间任一张。
1. 有效增量看三点 diff；怀疑改动已被别的 PR 抢先合入时用**树对树**：`git diff <branch> gitea/main -- <files>` 逐文件零差 = superseded，关闭并留裁决（#120 先例）。
2. 定向测试：只跑该单触碰模块的 tests；全量留给批次门禁。
3. handoff 写了 live 判据的，**独立复算读数**，不抄执行方数字。
4. 合并走 API：`POST /repos/a77/finance-workspace-private/pulls/{n}/merge` body `{"Do":"merge"}`。`mergeable` 卡 CHECKING 不动 → 读 `docs/handoffs/2026-08-18-acceptance-followups.md` §1 与 `docs/verification/2026-08-18-acceptance-followups-closeout.md` §1（应急面、已清队列、被否的路）。`mergeable=false` 且 `conflicted_files` 有台账路径 = 真冲突，提醒对方 rebase，不代解。
5. 裁决全文落 PR 评论。台账只留一行。

**完成判据**：该单验收标准每一条都有你自己复算的读数；PR 状态 = merged，或带裁决关闭。

## 3. 批次门禁

全部合并后在 main tip 上跑 AGENTS.md「合并纪律」节的四件套命令（webapp 没被动到也照跑）。数字对照台账最近一次门禁行，只允许持平或增长。

**完成判据**：四件套全绿 + 收据树 SHA == main tip。

## 4. 切 8792（链切五步）

链切用下面五步。`scripts/deploy_workbench_runtime.sh` 面向的是「rsync 进现有快照」的旧形态，只在快照目录不换时用。

```bash
# ⚠️ 这条 fetch 不能省（2026-08-18 实测补入）：验收 session 总是刚合完 PR 才切，
# 那一刻 finance-workspace-private 的 gitea/main **必然落后**（本次落后 10 次合并）。
# 少了它，rev-parse 拿到旧 sha，8792 会被钉在合并前的 revision，而三项验证全会通过
# ——因为它们只校验「加载的代码 == 那个 sha」，不校验「那个 sha == 主干最新」。
git -C /Users/a77/finance-workspace-private fetch gitea main
sha=$(git -C /Users/a77/finance-workspace-private rev-parse gitea/main)
git -C /Users/a77/finance-workspace-private worktree add --detach \
  ~/.finance-runtime/finance-workspace-${sha:0:12} "$sha"
launchctl bootout "gui/$(id -u)/com.a77.finance-workbench"
/bin/ln -sfh ~/.finance-runtime/finance-workspace-${sha:0:12} /Users/a77/finance-workspace-runtime
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.a77.finance-workbench.plist
```

验证（三项全过才算切完）：

1. `GET :8792/api/readiness` checks 全 true（预热冷启最长约 3 分钟，热缓存 ~1 分钟内）。
2. `GET :8792/api/health` **三读**：`source_revision` == 新 sha12、`source_dirty=false`、`code_matches_repo=true`。
3. grounded 探针：长电题、生产 env 形状（`cwd` 与 `PYTHONPATH`、`WORKBENCH_REPO_ROOT` 都指 `/Users/a77/finance-workspace-runtime`，`FINANCE_WS=/Users/a77/finance-workspace-private`），收据落 `~/.finance-runtime/live-probe-traceability/`。

   ⚠️ **判据已更新（2026-08-19）**：原文写「判据 `market_data_source=duckdb`、`snapshot_date` 新鲜」，
   但这两个字段名在当前收据 schema 里**都不存在**——`smoke_workbench_self_use.py` 的输出与
   run 目录的 `report.json` 都没有它们。照旧抄会得到「字段找不到 = 判据不过」的假红，
   或者更糟：以为查过了其实没查。改用**本仓 Phase 3 埋点**验同一件事（口径就在证据里）：

   ```bash
   R=<FORESIGHT_USERS_DIR>/<user>/runs/<run_id>      # 生产 8792 的是
                                                     # ~/.local/share/finance-workbench/users
   python3 - <<'PY'
   import json, collections
   ep = json.load(open(f"{R}/continuous-episode.json", encoding="utf-8"))
   cal = collections.Counter()
   def walk(o):
       if isinstance(o, dict):
           if o.get("caliber"): cal[o["caliber"]] += 1
           for v in o.values(): walk(v)
       elif isinstance(o, list):
           for v in o: walk(v)
   walk(ep); print(dict(cal))
   PY
   ```

   通过读数：出现 `fact_*` 口径（个股题应见 `fact_stock_daily`）、`payload_field_names`
   含真实列名、数据日 == 库内 `max(trade_date)`、答案里无「本轮没有连接本地市场数据」、
   `degrade_count=0`、`secret_scan.hit_count=0`。
   2026-08-19 切 `8bbfc4e41a5a` 时的实测读数：`dataset=stock_daily`×12 /
   `caliber=fact_stock_daily`×4，数据日 2026-08-18 == 库内最新。

回滚 = 反向 `ln -sfh` 到上一快照目录（历史快照都保留在 `~/.finance-runtime/`）+ bootstrap。

切后补打 gitea 备份：`tar -czf ~/backups/gitea-$(date +%Y%m%d)-post<PR号>.tar.gz -C /opt/homebrew/var gitea`。

**完成判据**：三项验证读数齐 + 备份文件在 `~/backups/`。

## 5. 回写台账

顶部插「更新：」密报行（处置结果 / 门禁数字 / 切换读数 / 收据路径 / 升格项），连同新 handoff 走 docs PR 合入。台账顶部是并发追加热点，rebase 重解冲突是常态。

**完成判据**：台账行合入 main；需要用户拍板的事项在行里显式标「待裁决」。

## 坑（都踩过）

- 并发 session 可能正在交付下一批：只动自己队列里的分支；发现冲突提醒对方，不代解。
- pre-commit 有层级 / 路径字面量 / 字段契约等门禁，docs-only 提交也会全跑，属正常。
- 台账/handoff 里引用的收据路径要真实存在——写行前先 `ls` 一遍。
