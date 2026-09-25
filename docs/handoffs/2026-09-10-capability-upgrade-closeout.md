# 2026-09-10 能力升级整包收尾：W5 口径定案 + W6/W7 夜跑手动补通 + 串行补验队列

> 配套在途交接：`docs/handoffs/inflight/ops-capability-upgrade-closeout.md`（≤3K，本文件是展开版）。
> 本文件写完不改；后续进展覆写 inflight 那份。

## 背景（不读会误判后面每个决定）

- 09-09/10 能力升级 10 单 + I1/I2 全部合入 main（#709–#716，tip=6626f12f，生产 8792 已跑此版本）。
  判官修复（#712）已在本会话用 evidence-judge.md 原始命令对生产代码实测复核通过（同源新页 new_evidence=1/
  repair_allowed=True；扩展输出进 extension_outputs 不再连坐）。**合并完成 ≠ 验收达标**：网关依赖的
  补验（01 统计批 / 04 WP6 / I2 live / 05 材料轮 / 10 配对批）与 00 的 after 臂都还没跑。
- 00 的基线 30 题已于 09-10 下午收口（28 completed + 2 engine_missing），但 09-10 09:47–14:19 网关
  全线 502 污染了其中若干轮次；00 闸门只数终局状态，I1（未合）按轮次归因，两者对「502+零草稿算不算
  干净」口径冲突——这是 W5。
- W6：`fact_theme_flow_daily` 停在 09-02；W7：launchd 夜跑主检出停在 09-08 的 detached b4a35fa2
  （**不是 main 祖先**，是 event-pricing 侧枝头；fwp-wt-spry-soaring-summit 持有 `event-pricing-slice1`
  分支指向它，内容不丢），没有 plan=local 支持，导致 09-10 晚 18:30 sync / 20:40 finalize 双双中止。
- 主检出 `/Users/a77/finance-workspace-private` 有 **96 个他人未提交 WIP**（09-10 01:12–01:18 改动，
  无 handoff）：theme_flow 的 sector-basket 聚合回退链路（`sync_theme_capital_from_baskets.py`，未提交
  未测试）、L2 闲鱼网盘链路（`scripts/moneyflow/run_l2_from_share.py` 等全套）、`nightly_full_review.sh`
  重写（已同步进 ~/.local/bin/）。**不要替作者跑这些代码，不要动这些文件。**
- `/Users/a77/finance-workspace-runtime` 是指向**生产工作树** `~/.finance-runtime/finance-workspace-
  6626f12fb694` 的软链。拿它当 CODE_ROOT 跑带状态写入的脚本会把 `skills/daily-full-review/state/`
  与 `db/snapshots/increments/` 写脏生产树（今晚已发生并已清理迁回数据树）。

## 今晚已做（按发现顺序）

1. **W5 reclassify（只读）**：用 I1 树 `/Users/a77/fwp-wt-i1-attribution` @ 01de7e94 的
   `capability_benchmark reclassify` 对基线终件 `~/.finance-runtime/capability-benchmark-00/runs/
   20260910T105119Z-cb00-baseline-372d047c0b0f.json` 重审，派生件：
   `….reclassified-i1-01de7e94.json`。**结果：clean 13 / recovered 10 / unavailable_final 5 /
   engine_missing 2**。假干净是 5 题不是预估的 3 题：`cb00-material-01`、`cb00-material-02`、
   `cb00-calc-01`、`cb00-continue-01`、`cb00-continue-02`（事件链全 502，invalid_repair_finish /
   repair_deadline_exhausted / invalid_model_finish，无有效草稿）。抽查 3 题核实分类正确：
   material-01 答案是降级壳、continue-01 续研轮（题眼）是 gap 模板、continue-02 中报数字轮全灭。
   另发现 5 个判官轮 judge_status=unavailable（judge 也烧了配额，聚合时须单列）。
2. **评审包拦截**：`review-pack-20260910/` 已落 `HOLD-DO-NOT-REVIEW.md`。该包含 5 题假干净的降级
   答案，且 decoy 配对的 calc-01 本尊就是无效降级答案（反向验证在本包不成立）。**勿投入评审**；
   五题重跑后重出评审包（新 seed 目录，不覆盖旧目录）。
3. **W6/W7 手动补通 09-10**（命令收据在 `logs/daily-full-review.out.log` 22:15 起两段）：
   - 第一次裸跑 rc=3：runtime 树缺 `shared` 软链（已 `ln -sfn ~/.claude/shared` 修复，该树本就
     不在 git 内）+ preflight 不感知 plan 误要 fupanhui 登录（plan-local 修复在未合分支
     `fix/preflight-plan-local` @ 4baa6516，fwp-wt-backfill-0908 树）。
   - 第二次带 `--skip-preflight` 成功：staging 换名 `run_id=4db34a41ddeb`，`fact_market_daily` 到
     09-10，same-day-gate plan=local **COMPLETE**（13 张 fupanhui-only 表被正确裁剪，theme_flow
     陈旧不再挡当日闸）。所有 local 步骤走 main tip 代码（eastmoney 快照、stitch、sector/limit/
     overview/editorial/stage/high/mainline/core-stock locals、features）。
   - 跑法关键：`FINANCE_SYNC_CODE_ROOT=/Users/a77/finance-workspace-runtime` 覆盖 + 其余 env 照抄
     plist（FINANCE_DATA_ROOT/FINANCE_WS=private、REVIEW_SYNC_PLAN=local、FINANCE_PYTHON=主检出
     .venv-workbench/bin/python）。
   - **finalize/生成段没补跑**：其闸门含 L2 段，依赖 WIP 作者的 L2 链；09-10 日报未生成。需要时
     明天手动补。
4. **飞轮首个真实前向观察落地**：对生产 study `~/.local/share/finance-workbench/users/linxiaoqi5111/
   method_validation/475597e2e017a2…/` 手动跑 `method_validation.py daily`（代码=main tip 生产树，
   日志 `logs/method-validation-daily.log`）：旁路库重建 8.2s（labels 1,477,627 / outcomes
   1,680,220，水位全到 09-10）→ capture/2026-09-10/a378645a….json（members=403、streak3=0、
   signal=false → 不登记 checkpoint，符合「有信号才登记」设计）→ recheck 无到期对象 → standing
   刷新为 **downgrade**（历史演练 2 共同日不支持「连续双红更强」，min_n 20 未达，仅观察提示——
   这正是 memory_lookup 现在读到的立场）。跑后生产树 0 dirty。
5. **生产树卫生恢复**：sync 把 runlog 段 / quality-2026-09-10.json / 增量 tar.gz 写进了生产树，
   已全部迁回数据树对应位置并 `git checkout --` 复原。8792 /health 的 source_dirty 是启动时快照，
   不受运行期落盘影响，但任何重启后重算会暴露——已清零。

## 串行补验队列（网关依赖，严禁并行抢窗口；每项跑完看 retry-after/冷却再排下一项）

顺序即优先级。前 4 项建议交还原 00 agent（它持有 sidecar-8813 与 baseline 上下文）。

| # | 任务 | 前置 | 通过判据 |
|---|------|------|---------|
| 1 | **00 五题 resume 重跑**：material-01/02、calc-01、continue-01/02 | 网关确认可用（小额试单）；用 **I1 树代码**（resume 与 review-pack 共用 case_service_isolated）；sidecar 8813 同 rev 重起；臂标签不变 372d047c | 5 题四分类不再是 unavailable_final |
| 2 | **00 重出评审包 + 人工评审（≥20% 双评）+ aggregate** | #1 完成 | 新包 30 题无 unavailable_final；双评覆盖≥6 题；aggregate 报告与 mapping 一致 |
| 3 | **01 统计验收批**（明早 09:47 launchd 已排，跑前 `launchctl list` 确认不与其他臂同刻） | 网关 | progress/01.md 的统计判据 |
| 4 | **00 after 臂**（对照 6626f12f，same cases） | #2 完成、网关稳定 | 四分类终件 + 对照报告 |
| 5 | 04 WP6 补验 | 网关 | 见 blocked/04.md |
| 6 | I2 graph_lookup live 补验 | 网关 | 见 I2 交接 |
| 7 | 05 材料轮 3 题 | 网关 | 见 05-acceptance/ |
| 8 | 10 完整配对批（01–10 + I1/I2 每单 1 成功 1 失败形状 × 新 CLI × 持久判官） | 网关 | 持久判官留痕 |

网关探活别空烧：用 Keychain 凭证小额试单（`gpt-5.6-sol`/`gpt-5.6-terra` 的 cooldown 与 502
`no auth available` 都是网关侧状态，agent 侧无法修）。**上游认证故障时 8792 面向用户的模型链也不可用，
别再堆空跑轮。**

## W7 永久解（明天协调后做，别今晚偷跑）

主检出推进 b4a35fa2 → 6626f12f（347 commits / 554 文件）：

- **先决**：WIP 作者提交或自行 stash 其 96 文件（含 `market_feature_store/cli.py`、
  `consumption_registry.yaml`、`check_daily_review_data.py`、`skills.registry.json`、`CLAUDE.md`、
  `nightly_full_review.sh` 等 13 个与 main 变更重叠的文件）；或用户明确授权 stash→checkout→pop。
- 推荐路径：`git stash push -u`（在 00 工作区留副本备份）→ `git checkout --detach 6626f12f…` →
  `git stash pop` → 逐冲突人工解。**不要** `git checkout --merge`（冲突标记直接进工作树，污染他人
  进行中代码的语境）。
- 完成后 launchd 全链自愈（plist env、wrapper、~/.local/bin 脚本均已就位，唯一缺的就是代码版本）；
  同时 plan-local preflight 分支合入后 `--skip-preflight` 也不再需要。
- 替代路径（次选）：WIP 作者完成他们未完成的 plan-local 扩展（他们改过 `run_review_sync.py`，但
  该树的 run_review_sync.py 本身还是旧的、没有 local——他们的改法意图不完整，勿替他们猜）。

## 待合入清单（都不在我今晚职责内，已核实存在与内容）

1. `fix/preflight-plan-local` @ 4baa6516（fwp-wt-backfill-0908 树）：plan=local preflight 不再要
   CDP/fupanhui 登录——正是今晚撞的坑，合入后夜跑裸跑即可。
2. 09 树 `e480e6c7`：LLM_COMPAT_PAYLOAD 按模型前缀改写/摘除出站字段（kimi-k3 system+tool_choice
   拒答修复，20:30 提交未合）。
3. I1 树 `01de7e94`：四分类归因 + reclassify 子命令——**00 重跑与 aggregate 的口径应以它为准，
   建议在 after 臂起跑前合入**，否则基线与 after 两臂口径不一致。

## 其他排期

- **RAG 索引重建，09-14 前**：`~/knowledge-base-private/.rag_index/meta.json` built_at=2026-08-31，
  14 天上限将整库判 stale。重建走 KB 仓 `scripts/rag_build_full.py` + `publish_rag_index.py`
  （169K chunks 重活，别与夜跑同刻、别在网关修复期跑）。
- **B7/B8 小修单**：B7 题内回指误判跨轮追问（00 基线 2 题 engine_missing 的根因）、B8 直答车道缺
  研究先验块。未开单。
- **05 的 5 项接口收口**：见 05-acceptance/05-acceptance-matrix.md。
- **09-10 日报**：今晚 finalize 未补跑，日报未生成；需要则明天手动 finalize（注意 L2 闸依赖 WIP 链）。

## 不要做的（附理由）

- 不要替 WIP 作者跑 `sync_theme_capital_from_baskets.py` 回填 theme_flow 09-03~09-10：代码未提交
  未测试，跑半截留 inconsistent 状态比缺数据更难收拾。theme_flow 缺口只影响 river.py 等读侧新鲜度，
  不挡 plan=local 的当日闸。
- 不要今晚推进主检出：他人 WIP 在场，stash-pop 冲突会让我替别人做语义判断。
- 不要长期使用 `FINANCE_SYNC_CODE_ROOT≠FINANCE_DATA_ROOT` 的跑法：sync 的状态文件按 CODE_ROOT
  相对路径写，会污染代码树（今晚实证）。它是今晚的应急手法，主检出推进后即作废——所以不工具化。
- 不要评审 `review-pack-20260910/`：已 HOLD。
- 00 after 臂不要在 I1 合入前跑：口径分裂会让 30 题 × 两臂的对照失去意义。

## 验证收据索引

- reclassify 派生件：`~/.finance-runtime/capability-benchmark-00/runs/…reclassified-i1-01de7e94.json`
- sync 日志：`logs/daily-full-review.out.log`（22:15 失败段 + 22:18 成功段，含逐模块表）
- staging 收据：主库内 run_id=4db34a41ddeb
- 门禁复核：`check_daily_review_data.py 2026-09-10 --phase data --plan local` → COMPLETE
- 飞轮：`logs/method-validation-daily.log`；capture 收据在 study 目录
- 判官复核：evidence-judge.md 两条原始命令对生产 8792 代码实测（会话前段，函数级复现）
