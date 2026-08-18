# 2026-08-18 验收批收尾移交 — 四项待办 + 一项记录

验收 session（2026-08-18 上午）处置完 9 张交付（8 合并 + #120 superseded 关闭，明细见台账 10:50 行与各 PR），主干门禁全绿后已把 8792 切到 `4a3bb31366c2`。本单移交验收过程中暴露、但不属于验收本身的四件事。领单前先读对应「证据」段，别重跑已被否掉的路。

## 1. Gitea pr_patch_checker 队列不消费（P1，影响所有后续 PR 的可合并性）

**现象**：PR 的 `mergeable` 恒 `false`、DB 里 `pull_request.status=1`（CHECKING）不动；API merge 返回 405「Please try again later」。首例 #168（08-18 凌晨），卡死数小时。

**证据与时间线**：
- 本地 `git merge-tree` 证明 #168 与 main 干净可合，但 Gitea 端状态不刷新。
- 已试且**无效**：Gitea 重启、`gitea manager flush-queues`、往分支推空提交、关/开 PR。
- 10:52 开的 #187 秒出 `mergeable=true`——新 PR 的同步 testPatch 路径活着，或队列已部分自愈；但存量卡死是实锤，两者不矛盾。

**应急工作面（已用于 #168，不可常态化）**：`sqlite3` 把 `pull_request.status` 置 `2`（MERGEABLE）后走 API merge。安全性兜底：merge 时 Gitea 仍做真 git 合并，真冲突会在那一步失败，不会静默合坏。

**待办**：确诊 LevelDB 队列残留——停 Gitea → 备份后清 `/opt/homebrew/var/gitea` 下 `queues/` 对应目录（dedup 残留的嫌疑最大）→ 起服观察；不行就升级 homebrew gitea。改动前后都有备份可回退（`~/backups/gitea-20260818-post187.tar.gz` 是最新锚）。

**验收标准**：新开一张测试 PR，30s 内 `mergeable` 自动出结果；再对任一存量 open PR 触发 re-check（关/开或推提交），状态能自动刷新，不再需要 DB 手术。

**被否方案**：① DB 手术常态化——绕过一致性检查，只准应急；② 等自愈——#168 实测数小时不动。

## 2. 验收 token 缺 `write:issue` scope

**现象**：`POST /repos/.../issues/{n}/comments` 返回 403，`required=[write:issue], token scope=write:repository,write:user`。

**影响**：验收裁决没法以评论落在 PR 时间线上，只能追加进 PR 描述（#120 已如此处理，裁决全文在其描述尾部）。

**待办**：给验收用途重发或新增一枚含 `write:issue` 的 token（Keychain `gitea-local` 同位更新或另立条目）。最小权限即可，别顺手加 admin。

**验收标准**：对任一 PR POST 评论返回 201。

## 3. KC-17 实体三态的 A3 旁路复验（执行方自留项，前置已全齐）

**背景**：#159（实体解析三态，R15-A3 前缀吞没修复）已合并、8792 已切到含它的 `4a3bb31366c2`。执行方在 KC-17 handoff 里自留了「合入后旁路复跑 R15 A3」，当时前置未齐，现在齐了。

**待办**：按 R15 考卷 A3 用例旁路复跑（切前形状=实体前缀被吞、答非所问），确认产线三态行为：resolved 直答 / candidate 附澄清 / unresolved 反问。

**验收标准**：A3 题不再前缀吞没；收据落 `~/.finance-runtime/live-probe-traceability/`，并回写 KC-17 handoff 的验收节。

## 4. #177 与主干在台账文件有内容冲突（KC-C/D session 自理）

`fix/eval-launchd-loop-repair` 与 main 在 `docs/handoffs/inflight/main.md` 顶部相邻缝冲突（验收 session 的 #187/#188 台账行与其并发追加）。需其 rebase 到最新 main 重解后再合。只是提醒，不要替它解——该分支还在人家手里。

## 记录（不需要动作）

- **8792 已切 `4a3bb31366c2`**：bootout→链切→bootstrap 一次成，T+49s ready，readiness 13/13、三读 dirty=false。
- **#167 生产闭环**：grounded 探针（长电题、`use_llm=False`、生产 env 形状）`data_repo_root=/Users/a77/finance-workspace-private`、`market_data_source=duckdb`、`snapshot_date=2026-08-17`、「本轮没有连接本地市场数据」消失。切前对照收据 `run_20260818_003133_360184`（`source_date=2026-07-15` + 断连降级）。本次收据 `~/.finance-runtime/live-probe-traceability/cutover-4a3bb31366c2-20260818.json`。
- **gitea 备份**已按「代码合并后补打」约定落 `~/backups/gitea-20260818-post187.tar.gz`（1.2G，含 queues/，正好是队列故障现场的取证快照）。
- 回滚锚：`finance-workspace-d1be2d0c1fd3` 保留，随时可反向链切。
