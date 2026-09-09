# 能力集成执行进度（PROGRESS）

> Spec：`docs/superpowers/specs/2026-09-09-capability-integration-and-live-research-design.md`
> 执行分支：`feat/capability-integration`（基于 `codex/docs-capability-integration-spec` a06deea7 = gitea/main b952439a + spec）
> 执行树：`/Users/a77/fwp-wt-capability-integration`。换会话先读本文件与 BLOCKED.md。
> 本文件由执行者维护；证据等级标注 [实测]/[推断]，未标注默认 [实测]（当次命令跑出）。

## 任务 0 开工回执（2026-09-09 21:55）

1. 树/分支：执行树 `fwp-wt-capability-integration` @ `feat/capability-integration`；主检出（脏、detached b4a35fa2）留给原使用者，不动。
2. 远端：gitea/main=b952439a 已 fetch；生产 8792 healthy @ac013255（=#696 合入点，含 05/07/09 首刀），落后 main 12 提交；#697/#699 投影修复已合 main、未上生产。
3. 知识库：kb gitea/main=0f7ce1dfd（03 已合）；kb 主检出 af2f708 落后 5 且脏（保留原树）；全部既有 kb 树均不含 03 → 已新建干净运行树 `/Users/a77/kb-wt-cap03-runtime` @0f7ce1dfd。
4. live 端口→树：00→8813（**批次进行中** PID 30453，user=cb00-baseline，21:39 起，勿动）、02→8802@360ef6f0、04→8794@51ee71f8 与 8795@2ebbc04f、06→8811(base)/8812@de799ff8、08→8808@09c16461、09→8847@adcd4830（含 #697/#699）、10→8815(base)/8816@0d942702、生产→8792、launchd 能力 sidecar→8796@40fd5a84。
5. 模型/判官：网关 `http://127.0.0.1:8080/v1`，模型 `gpt-5.6-sol`；判官 grok 1.0.24（经 `~/.grok/bin/grok` 符号链接）；生产 ASK_CONTINUOUS_RUNTIME=on、ASK_AGENT_LOOP=auto、ASK_EVIDENCE_JUDGE=auto。凭据不落本文件。
6. 用户/数据根：生产 users=`/Users/a77/.local/share/finance-workbench/users`，user=`linxiaoqi5111`；FINANCE_WS=`/Users/a77/finance-workspace-private`；主库 `db/market_feature_store.duckdb`。
7. 日程：`daily-full-review-sync`（20:10 前后）与 `-finalize`（20:40 → `~/.local/bin/nightly_full_review.sh`，mtime 08-20）今日 last-exit 均 =2 待查；包装脚本内无 method_validation 接线；`checkpoint-recheck` loaded exit 0；`fidelity-forward-acceptance` loaded exit 1（fidelity 车道，非 07）。
8. 题库/规则指纹（冻结）：questions `d987df999f866873`、sealed-manifest `4ef1fd08f5db09cf`、capability_benchmark.py `6a04879c9924f07c`，均 @00 分支 `baseline/capability-benchmark-00` b044b61c；公开题 20、协议字段 4。
9. 代码地图：ready（n=22076 @b4a35fa），doors 查询正常返回。
10. 批次纪律：本轮新增 live 一律串行排队，调度责任人=本执行者；不停止、不复用他人进行中批次的用户域。

## 冻结条件台账（§2.2-4）

| 项 | 值 | 来源 |
|---|---|---|
| 题库（20 公开） | sha256 前 16 位 `d987df999f866873` | `fwp-wt-capability-benchmark-00/intelligence/eval/fixtures/capability-benchmark-2026-09-09.questions.json` |
| 密封题清单（10 密封） | `4ef1fd08f5db09cf`（manifest 含 hidden_case_ids/rubrics 哈希/verify_cmd；执行者不读密封判分点） | 同目录 `.sealed-manifest.json` |
| 评分实现 | `6a04879c9924f07c` @ b044b61c | `intelligence/eval/capability_benchmark.py`（I1 允许改分类实现，改后此指纹按新提交重记，题面/密封判分点/权重/阈值不变） |
| 判官 | grok 1.0.24（`~/.grok/bin/grok` → `../downloads/grok-1.0.24-macos-aarch64`） | ls -la 实测 |
| 模型 | `gpt-5.6-sol` @ `http://127.0.0.1:8080/v1` | 生产进程 env（ps eww，已脱敏） |
| 基线 live 占用 | cb00-baseline 批次进行中（PID 30453 → 8813@372d047c） | ps + runs 目录 21:49 仍在产出 |

## 环境与身份台账（§2.2-2）

- 金融仓：gitea/main=b952439a；生产 8792 加载指纹 `4e2acfe59bd26d9a…`（code_matches_repo=true，878 模块）@ `/Users/a77/.finance-runtime/finance-workspace-ac0132553aae`。
- 知识库仓：gitea/main=0f7ce1dfd（#146 = 03 research-map 合入）；干净运行目录 `/Users/a77/kb-wt-cap03-runtime`（detached @0f7ce1dfd，status clean）；kb 主检出与 kb-runtime(669d3207a) 均不含 03，不用于本轮研究查询。
- I2–I5 落点存在性 [实测]：main 已有 `scripts/method_validation.py`、`intelligence/services/method_validation/`、`research_project.py`、`followups.py`、`runtime/continuous_turn_adapter.py`、`market_feature_store/sync/sync_akshare_sw_l1_daily.py`；`services/data_requests` 仅在 08 分支（fwp-wt-demand-driven-data，sidecar 8808）——I4 前先收 08 分支。
- `capability_benchmark.py` 仅在 00 分支，main 无此模块——I1 在 00 分支之上开工作分支，不动 00 原树（其 sidecar/批次在跑）。

## 已被别人修好的缺口（§2.2-1，随证据更新）

- 09 投影修复 #697（项目对象取众数/数据截止回溯）、#699（对象子串归并）已合 main [实测 git log]；生产 8792 尚未包含（生产=ac013255=#696）。09 运行时树 8847@adcd4830 已含两修。
- #698 stitch iFinD value 源白名单已合 main [实测 git log]。
- 05 材料轮复验 runbook #703（`--user cap05-prod`）已合 main [实测 git log]。
- 07 #707「方法飞轮真实验收记录＋生产激活」已合 main，**但为 docs-only 提交**（lessons/handoff/progress/spec 四文件）[实测 git diff --stat]；`nightly_full_review.sh` 无 method_validation 接线 [实测 grep]。「生产激活」的真实形态待读 progress/07.md 后落到 I5 计划。
- （待任务包通读报告后补全本节）

## 阶段计划：落点/依赖/测试/验收命令（§2.2-3）

（待任务包通读报告后填写；每项包含：精确修改文件、依赖提交、定向测试、实际验收命令。）

## 执行状态表

| 项 | 状态 | 负责标签 | 提交 | 原件 | 下一命令 |
|---|---|---|---|---|---|
| 任务 0 | 进行中（回执已立，阶段计划待任务包报告） | 集成执行者 | — | 本文件 | 填「阶段计划」后转 I1 |
| I1 | 未开工 | 00 | — | `~/.finance-runtime/capability-benchmark-00/users/cb00-baseline/runs/run_20260909_205227_971715/continuous-episode.json`（漏判反例） | 在 00 分支上开工作分支 |
| I2 | 未开工 | 06/01/02 | — | — | 等 I1 后按依赖序 |
| I3 | 未开工 | 06/09/04/10 | — | — | 依赖 I2 |
| I4 | 未开工 | 08/06/09 | — | — | 需收 08 分支 |
| I5 | 未开工（可与 I1 并行） | 07 | — | — | 追 #707 激活实态 |
| J1/J2/J3 | 未开工 | 集成执行者 | — | — | I2/I3/I4 就绪后 |
| 00 对照 | 未开工 | 00 | — | — | 候选冻结后 |
