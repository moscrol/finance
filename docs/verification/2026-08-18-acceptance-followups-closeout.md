# 2026-08-18 验收 follow-up 收口

领单：`docs/handoffs/2026-08-18-acceptance-followups.md`（#189）。未切、未重启 8792（仍 `4a3bb31366c2` / pid 67921 / dirty=false）。#177 未动。

## 1. Gitea `pr_patch_checker` 队列 — 已清，验收过

**处置（11:17）**：`brew services stop gitea` → 备份 `~/backups/gitea-queues-20260818-111706.tar.gz`（31K，只打 queues/）→ 把 `data/queues/common` 挪成 `common.preclear-20260818-111706`（10:05 的 `common.stale-20260818` 原样留着，那是故障现场）→ `brew services start gitea`。起服后新 `common/` 自动建出。全量 1.2G 锚仍是 `~/backups/gitea-20260818-post187.tar.gz`。未做 DB 手术，未升级（homebrew 已是 1.27.2）。

**清之前的现状（避免重跑已否的路）**：新 PR 其实已经能出 `mergeable`（#187/#189/#190）；当时 `mergeable=false` 的 #175/#177/#179/#181 都是台账文件真冲突（`conflicted_files=["docs/handoffs/inflight/main.md"]`），不是 CHECKING 卡死。DB 里仅剩的 `status=1` 两行是已合并的 #16/#42 残骸。

**验收**：

| 探针 | 结果 |
|---|---|
| 新开 #192 | 创建后 0.1s `mergeable=true`，`status=2` |
| #192 空提交再推 | 0.3s 仍 `mergeable=true`，无 sqlite |
| 存量 #147 关/开 | 重开即 `mergeable=true`，`status=2` |

被否方案仍否：DB 手术不常态化；不靠自愈。

## 2. 验收 token 补 `write:issue` — 已补

**403 证据**（旧 token）：`POST /issues/189/comments` → `required=[write:issue], token scope=write:repository,write:user`。

**修法**：`gitea admin user generate-access-token --scopes write:issue,write:repository,write:user`（最小集，无 admin）。Keychain `gitea-local` / `a77-token` 同位替换；旧值备份到同钥匙串 `a77-token-prev`。token 名 `acceptance-write-issue-0818`。

**验收**：`POST /issues/192/comments` → **201**（comment id 896）。

## 3. KC-17 / R15-A3 旁路复验 — PASS

前置齐：#159 已合 + 8792=`4a3bb31366c2`。旁路 sidecar `:8797`（`:8796` 当时被他轨占用，未碰），`GROUNDED=0`，scratch user `live-probe`，用完已停。未写真本 `linxiaoqi5111`。

**切前形状**（R14 A3 `20260813T0155Z-r14-a3-postfix.json`）：「立新能源」被吞成 theme「新能源」→ `theme-research`，`evidence_bound=0`，答「现有证据不足」。

**本发** `run_20260818_111701_388149`（198.9s，completed）：

- `question_type=stock_deep_dive`，`matched_theme=null`
- 锚：`立新能源（001258.SZ）`，warning=`实体 立新能源 来自证券名单（未在知识库登记）`——有库 resolved，不是前缀吞
- 引用 **15** 条（G3+R8+D4）；对话稿写出 08-17 收 14.4 / +4.73% / 20.32 亿
- 图谱仍命中概念「新能源(10)」是暴露退化，不是路由被偷

离线三态（同一快照 + `FINANCE_WS`）：

| 问 | 库 | status / action / subject |
|---|---|---|
| 立新能源怎么看 | 生产 DuckDB | resolved / proceed / 立新能源 · `stock_deep_dive` |
| 立新能源怎么看 | `ENTITY_ANCHOR_SECURITIES_DB=0` | candidate / clarify / 立新能源+新能源 |
| 这东西怎么看 | — | unresolved / disclose |
| 新能源怎么看 | — | resolved / proceed / 新能源 · `theme_analysis` |

收据：`~/.finance-runtime/live-probe-traceability/kc17-r15-a3.json`（产物目录同 slug）。#159 Test plan 末条已勾。

## 4. #177 — 未代动

`fix/eval-launchd-loop-repair` 与 main 仍在 `docs/handoffs/inflight/main.md` 冲突。留给 KC-C/D session 自己 rebase。
