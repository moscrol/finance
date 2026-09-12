# fix/sync-code-root · 夜跑两个代码根钉死

## 状态：未推未合，等用户确认

`5b57d109` sync 代码根 / `6439ea77` 质检闸门代码根 / `198b95f0` finalize 源缺的档位 +
手动补跑入口 + 日更固定 local / 三份 handoff。

## 完成口径（别写成「事故已修」）

已修掉 `unknown plan 'local'` 的代码根原因，并验证装机配置已加载；
**真实同步、最终检查、方法日步尚未贯通验收**。

## 四处都是同一个形状：根解析缺省落到会漂的共用树

主检出树 `finance-workspace-private` detached 在 `b4a35fa2`、**落后 gitea/main 548
个提交**、带 64 个别人的未提交改动。它不能当任何运行时的代码根。

1. **sync**：`nightly-review-sync-staged.py:39` 的 `SYNC_ROOT` 缺省 `FINANCE_DATA_ROOT`
   → 那份 `run_review_sync.py` 的 `PLANS` 没有 `local` → `ValueError` rc=2 →
   **09-11（周五、交易日）整日没进库**。修：plist 显式
   `FINANCE_SYNC_CODE_ROOT=/Users/a77/finance-workspace-sync`（新建 detached
   worktree，跟随 `gitea/main`，只做这件事，不在上面开发）。
2. **质检闸门**：三处 `scripts/check_daily_review_data.py` 是裸相对路径，落在
   `cd "$WORKSPACE"` 之后 = 同一棵旧树；那份没有 `--plan`、表清单写死，
   plan=local 下必然少 `theme_flow` / `limit_advance`。同日同库实测（2026-09-10）：
   旧树 **exit=2 INCOMPLETE**（卡 `fact_theme_flow_daily`）/ CODE_ROOT 那份
   **exit=0 COMPLETE**。修：`REVIEW_CHECKER="$CODE_ROOT/scripts/…"`，缺了就停、
   不回退顶替。计划口径不用另传，`--plan` 缺省读 `REVIEW_SYNC_PLAN`，两个 plist 都有。

仓内源与装机副本**两边都改了**（`install_eval_launchd.sh` 是 `cp 源 → dest`）。
装机副本是外科式打补丁：它与仓内版有其它有意差异
（`docs/handoffs/inflight/chore-retire-feishu.md:71`），**别跑安装脚本覆盖它**。
两处原件备份为同目录 `*.bak-pre-*-20260912`。

背景、被否方案、三处走错又纠回来的地方（`plutil -lint` 不校验 XML 注释、
`active --help` 不是能力探针、`deploy_workbench_runtime.sh` 不更新 `scripts/`）
见 `docs/handoffs/2026-09-12-nightly-code-root-outage.md`。

## 未验证

- `--phase all` 在 09-10 仍红，红在「日报 md 不存在 / L2 三步无完成记录」——那是
  finalize 被守卫拦掉的后果，非独立阻塞，只能等一次完整跑通才能判。
- **未跑全量 pytest**（另一 agent 在并发跑，16 GB 机器不开第二份）。合入前补。

## 未决

1. **9-11 补数**：用户手动 `/daily-full-review`。照 SKILL.md 新写的一键入口跑
   （在 `finance-workspace-sync` 里、带 `REVIEW_SYNC_PLAN=local`），不要在主检出树跑。
2. **名单基线仍旧**：9-10 价格是新的，成分基线还来自 9-02；每天重算不会自动发现
   新概念、新成员。需要一条名单更新链。
3. **同花顺日更没接进 local 的 16 步**：代码已合、数据已首次灌入，但更新步骤挂在
   另一条同步链上，相关表实读仍停在 9-08。
4. 2、3 两条是数据面缺口，不在本分支改动面内，尚未立单。

## 关联分支（feat/method-closed-loop，非本分支）

LOG_DIR 顺序 bug → 对方修在 `22c60030`（我复验：45 赋值 → 46 mkdir → 61 引用）。
「旧 CLI + 新 wrapper」→ 修在 `607f53a6`：能力探针改用顶层 `--help` 的子命令列表
grep `[{,]active[,}]`，exit 2 的二义拆开（3 单列「已配置但失效」，`*)` 改中性措辞）。
我用真实新旧 CLI 复验过探针，旧=探不到走默认、新=探到走指针。
**`active --help` 不能当探针**（argparse 优先处理 `--help`，不校验子命令，两边都返 0）。
