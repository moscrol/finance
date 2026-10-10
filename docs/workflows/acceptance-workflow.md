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
- 真实会话用 `scripts/launch_workbench_sidecar.sh`；它在读取生产 launcher 后同时覆盖 `FORESIGHT_USERS_DIR` 与 `FORESIGHT_EPISODE_STORE=$USERS/.episodes`。只换用户目录不够：Episode 默认仍写 `$FINANCE_WS/state/episodes`。`FINANCE_WS` 保留用于读取正式行情，不为隔离会话伪造行情根；验收进程另用只读沙箱保护生产库、索引、配置和用户目录。
- Gitea API token 在 Keychain：`security find-generic-password -s gitea-local -a a77-token -w`。scope 最小集 `write:issue,write:repository,write:user`（2026-08-18 已补；缺 `write:issue` 时评论 403）。

**完成判据**：pytest 收据（`~/.finance-runtime/test-receipts/<ts>-<treesha>.json`）文件名里的树 SHA == 你正在验的树。

## 2. 逐张验收

0. **别信 Gitea 的 `mergeable`**（2026-08-18 实测补入）：#178–#194 十张全报 `mergeable=true`，实际 #190/#194 有真冲突，与 patch-checker 队列故障同源。自己探：
   `git merge-tree --write-tree gitea/main <branch>`，exit 0 = 干净，非 0 时输出里有 `CONFLICT` 行。
   另外先确认队列是不是**堆叠链**：`git rev-list --left-right --count <前一张>...<后一张>`，左侧为 0 = 后者含前者，此时链内不能改序、也不能单独打回中间任一张。
1. 有效增量看三点 diff；怀疑改动已被别的 PR 抢先合入时用**树对树**：`git diff <branch> gitea/main -- <files>` 逐文件零差 = superseded，关闭并留裁决（#120 先例）。
2. 定向测试：只跑该单触碰模块的 tests；全量留给批次门禁。
3. handoff 写了 live 判据的，**独立复算读数**，不抄执行方数字。
   复算前先过**生效模型准入**（spec `2026-09-02-capability-amplification-output-gate-design.md` §3.5.4 硬门 3；2026-09-30 补入，起因 09-29 GLM 重写消融预设 `glm-5.3`、实际跑的是 `glm-5.3-flash`）：
   `.venv-workbench/bin/python scripts/check_model_admission.py --expect-model <要测的模型> <run 目录或产物>...`
   有子研究时附 `--episode-store <实际 store 根>`；缺失分支不得放行。2×2 的 `analyze --plan` 自动从每条 artifacts 重算准入，人工 admission_exit 仅作审计。，exit 0 才算读数；1 = 错配，读数作废；2 = 证明不了（无带回的 model / 有「未回」），不得据此下能力结论。
4. 合并走 API：`POST /repos/a77/finance-workspace-private/pulls/{n}/merge` body `{"Do":"merge"}`。`mergeable` 卡 CHECKING 不动 → 读 `docs/handoffs/2026-08-18-acceptance-followups.md` §1 与 `docs/verification/2026-08-18-acceptance-followups-closeout.md` §1（应急面、已清队列、被否的路）。`mergeable=false` 且 `conflicted_files` 有台账路径 = 真冲突，提醒对方 rebase，不代解。
5. 裁决全文落 PR 评论。台账只留一行。

**完成判据**：该单验收标准每一条都有你自己复算的读数；PR 状态 = merged，或带裁决关闭。

### 方差门

单次探针没有显著性（N=1 的 `degrade_count` / 判官超时都能翻结果）。同 rev 同题 N 次翻转率由 `scripts/eval_variance_baseline.py` 出收据（`intelligence/eval/runs/*-varN.json`）。翻转率只许在干净的同 rev 同题复跑上算，禁止跨一次修复比。

**观测差异小于基线翻转率，不得下回归/改善结论。** 公式：每题 `flip_rate = count(primary_outcome ≠ mode) / N`，基线翻转率 = 各题均值。`--decide --observed-delta D --baseline-flip R` 在 `D < R` 时返回 `no_call`。内容质量对照用收据里的 `content_flip_rate`（已剔除判官桶）；含判官噪声的门用 `baseline_flip_rate`。

`judge_unavailable` 类 degrade 单列，不计入内容质量（W2 分类；W2 落地前把 `judge_status ∈ {unavailable, None}` 或 timeout 记入该桶，用现有字段，不上新的 LLM 判官）。

## 3. 批次门禁

全部合并后在 main tip 上跑 AGENTS.md「合并纪律」节的四件套命令（webapp 没被动到也照跑）。数字对照台账最近一次门禁行，只允许持平或增长。

**完成判据**（2026-08-27 起从人眼比对改为 exit code，工单 §P1-a；起因 #444 分支尖收据冒充批次门禁、合并后 main tip 无收据零报警）：四件套全绿，且下面命令 **exit 0**——

```bash
git fetch origin main   # 2026-09-30 起 GitHub origin 是主干，Gitea 只收定时备份、会滞后；不 fetch 则对着过期主干验
.venv-workbench/bin/python scripts/check_test_receipt.py <收据路径> \
  --expect-revision "$(git rev-parse origin/main)" --base-drift-max 5
```

exit 0 只对「命令里那个 `origin/main` 解析出的 SHA」成立；报告时把该 SHA 写进台账行。
`--expect-revision` 治「收据证明的是另一棵树」（全等比较，防 startswith 削弱），
`--base-drift-max` 治「分支基座落后主干 N 张合并仍拿分支绿冒充合流绿」。
收据不在 main tip 上 → 先在 main tip 重跑全量，不许拿旧收据凑数。

前端四项及 E2E 用 `scripts/run_frontend_gate.py` 生成独立收据：

```bash
.venv-workbench/bin/python scripts/run_frontend_gate.py \
  --tree <独占的固定检出根> --expect-revision <完整提交SHA> \
  --output <树外的新运行目录> \
  --workbench-port 18981 --re06-port 18984
```

该入口顺序执行依赖安装、lint、typecheck、test、build、test:e2e，使用当前 Python 解释器启动测试服务；端口与配套 URL 一起设置。测试服务的部署账本强制落到本轮输出目录 `deploy-ledger.jsonl`，覆盖继承或显式传入的 `FINANCE_DEPLOY_LEDGER`，收据的 `deploy_ledger` 记录该路径；它只是验收产物，不并入 canonical 账本。收据保存每步退出码、日志哈希和首尾 Git 身份。只有 `exit_code=0`、`complete=true`、`identity_stable=true` 且 `dirty=false` 才可采信；首尾 revision 都必须等于要求的完整 SHA。Git 查询失败不能解释为干净。任一命令失败或身份变化均返回非零，已有输出目录拒绝覆盖。

首尾采样不能证明期间没有发生又恢复的改动，因此仍要用独占检出。历史收据缺字段时保留原件，另起目录重跑；不得把今天的干净状态补写成过去的观测。`git status` 相同也不等于内容相同，复核既有脏树时还要比较二进制 diff 与未跟踪文件内容哈希。

## 4. 切 8792（准备、切换与验证）

链切按下面的准备、切换和验证段执行。`scripts/deploy_workbench_runtime.sh` 仅面向不受 Git 管理的旧式 standalone 目录：必须显式设置 `WORKBENCH_REPO_ROOT=<干净源树>` 并传入 `--apply --expect-revision <完整SHA>`。它拒绝覆盖 Git worktree 快照，也拒绝 `intelligence/` 为软链的运行目标；版本快照只能新建再切链；无参数、未知参数和不匹配的版本均拒绝执行，`--help` 只显示帮助。旧版本没有参数解析，连 `--help` 都可能执行真实部署，禁止以运行旧脚本的方式探测用法，先读源码。

```bash
# ⚠️ 这条 fetch 不能省（2026-08-18 实测补入）：验收 session 总是刚合完 PR 才切，
# 那一刻本地的远端跟踪引用**必然落后**（当时落后 10 次合并）。
# 少了它，rev-parse 拿到旧 sha，8792 会被钉在合并前的 revision，而三项验证全会通过
# ——因为它们只校验「加载的代码 == 那个 sha」，不校验「那个 sha == 主干最新」。
# 2026-09-30 起主干是 GitHub origin；Gitea 只收定时备份，会更滞后，别从它取 sha。
git -C /Users/a77/finance-workspace-private fetch origin main
sha=$(git -C /Users/a77/finance-workspace-private rev-parse origin/main)
git -C /Users/a77/finance-workspace-private worktree add --detach \
  ~/.finance-runtime/finance-workspace-${sha:0:12} "$sha"
# ⚠️ 生产启动器用「快照目录/.venv-workbench/bin/python」起 uvicorn，新检出的快照没有 venv。
# 不补这条软链，bootstrap 后服务 exit 127 循环重启（2026-10-06 切 f3b97499aaff 实测停机约 4 分钟）。
# 软链被 .gitignore 忽略，不影响「快照干净」判据。先补软链、确认可执行，再进下面的 bootout。
ln -s /Users/a77/finance-workspace-private/.venv-workbench ~/.finance-runtime/finance-workspace-${sha:0:12}/.venv-workbench
test -x ~/.finance-runtime/finance-workspace-${sha:0:12}/.venv-workbench/bin/python
# 四叶过后，切换段只执行这一条（2026-10-06 起）；不要再重复手动 bootout / ln /
# ledger record / bootstrap，否则会造成二次切换或重复记账：
bash ~/.finance-runtime/finance-workspace-${sha:0:12}/scripts/switch_8792.sh "$sha" <切换记录目录>
# 脚本核对完整 SHA、快照 HEAD、快照干净、venv 可执行和运行链接，bootout 后确认服务
# 卸载且 8792 端口空出，再用新快照里的解释器记录 --port 8792 并 bootstrap；账本失败、
# 链接失败或三次 bootstrap 失败会尝试恢复旧链接、旧版本账本和服务；回滚同样等待卸载与端口释放。
# 回滚不完整退出 7，读 switch.log 定位。退出 0 / SWITCH_BOOTSTRAP_DONE 只说明切换命令成功，仍须切后验证。
# INT / TERM / HUP 会触发一次补偿；恢复期间忽略重复信号。SIGKILL、断电或机器故障无法由脚本捕获。
# 脚本不负责上面的 fetch / worktree / venv 软链，也不替代下面的 readiness、health、grounded 探针。
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

回滚也从已通过门禁的新快照运行同一 `switch_8792.sh`，参数传上一快照的完整 SHA 和独立回滚记录目录；不调用旧快照里未经本轮核验的脚本。它会按相同前置条件停服、等待卸载和端口释放、换链、用旧快照解释器记录 `--port 8792` 并启动。完成后仍做上面的三项验证，历史快照保留在 `~/.finance-runtime/`。

切后确认备份已覆盖新主干：`git ls-remote gitea refs/heads/main` 应等于新 sha（GitHub→Gitea 定时备份，见 `dual-remote-collaboration.md`「本地备份任务」；没覆盖就按那一节手动跑一轮 runner）。2026-09-30 之前的 `tar -czf ~/backups/gitea-…` 口径已被它取代。

**完成判据**：三项验证读数齐 + Gitea 的 `main` 已是新 sha。

## 5. 回写台账

顶部插「更新：」密报行（处置结果 / 门禁数字 / 切换读数 / 收据路径 / 升格项），连同新 handoff 走 docs PR 合入。台账顶部是并发追加热点，rebase 重解冲突是常态。

**完成判据**：台账行合入 main；需要用户拍板的事项在行里显式标「待裁决」。

## 无端口启动归属

`check` 对账被 `port=null` 的测试服务启动行阻断时，不删历史、不补造生产 switch，也不按脚本名或位置参数猜端口。
先核对同次运行的单进程 Uvicorn 日志（PID 与监听端口）以及启动后五分钟内的 health JSON（时区、代码根与 revision）。
将原件保留在稳定树外目录，使用 `deploy_ledger.startup_row_sha256(row)` 得到原行规范化 JSON 的 SHA256，再执行：

```bash
"$PY" scripts/audit_deploy_ledger.py attribute-startup \
  --target-sha256 "$ROW_SHA256" --port "$PORT" \
  --server-log "$SERVER_LOG" --server-log-sha256 "$LOG_SHA256" \
  --health-snapshot "$HEALTH_JSON" --health-sha256 "$HEALTH_SHA256" \
  --reason "已核同次运行的进程、端口、时间、代码根和版本"
```

默认只读；核对计划后加 `--apply`，只向同一本账追加 `startup_port_attribution`。原行保留，补记不成为新的启动或切换，不能改变后续事件的顺序。
读取器每次重新核证据哈希；证据丢失、变化、归属冲突或重复原行都恢复未知。只有 startup 可补记，switch 仍须在实际切换时显式记录端口。
`check/homes` 使用补记，旧版本读取器仍会保守报错，必须明确使用含此修复的代码根；这不是生产代码已升级的证明。
证据只是本机保存的运行观测，不是密码学签名认证。手工拼出的日志不构成可采信原件。

## 坑（都踩过）

- **`smoke_workbench_self_use.py` 的收据 schema 会漂，别照旧收据抄字段名**（2026-08-21 实测补入，与上面 §4 那条「字段找不到 = 假红」同型）。现版本**不再发** `source_revision` / `code_root` / `grounded` / `question` / `user`，换成了 `gate_receipt` / `gate_receipt_table` / `readiness` / `retrieval` / `content_degraded_count` / `judge_unavailable_count`。拿 08-19 的 `20260819-post-d2ebf693-changdian.json` 当模板去读 `source_revision`，会得到 `None` 并误报成「切换没生效」。**revision 一律以验证 ② 的 health 三读为准**，收据只用来看 degrade / secret_scan / 口径。
- **live 探针要先确认打的是哪条引擎链**（2026-08-21 实测补入）。`intelligence.eval.live_probe ask` 走 `POST /api/runs`，落中立泳道，产物目录里**没有** `continuous-episode.json`——挂在 episode 判官链上的东西（语义判官、公开稿护栏等）一个字段都不会产，但 run 照样 `completed`，**看起来像跑过了**。要验 episode 链必须走 `POST /api/conversations` + `POST /api/conversations/{id}/messages`（`skill_mode` 必填，`perspective_mode=neutral` 走中立）。判据：产物里有没有 `continuous-episode.json`。
- 并发 session 可能正在交付下一批：只动自己队列里的分支；发现冲突提醒对方，不代解。
- pre-commit 有层级 / 路径字面量 / 字段契约等门禁，docs-only 提交也会全跑，属正常。
- 台账/handoff 里引用的收据路径要真实存在——写行前先 `ls` 一遍。
