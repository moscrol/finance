# baseline/capability-benchmark-00

## 这个分支做什么
能力升级任务包 00 号单「用真实工作衡量能力增长」：30 道真实研究工作题（10 类 × 2 公开 + 1 密封）、评分规则、走 Workbench 真实对话门的 runner、匿名配对评审包与汇总（含反向验证）。合同在 `codex/docs-capability-upgrade-plan@b80decbd` 的 `docs/superpowers/plans/2026-09-09-capability-upgrade/00-*.md`；进度 `progress/00.md`，阻塞 `blocked/00.md`（同目录，本分支）。

## 决策与被否方案
- 选：新建题集只补「真实工作题」，与 6 套既有题集零重叠钉单测。否：复用冻结 30 题（与 28 题重叠 19 道，是方差回归集）。
- 选：题面公开、判分要点密封（sha256 入仓、本体在 `~/capability-benchmark-00-sealed-20260909/`）。否：全公开——判据被「照答案调」过。
- 选：入口只认 `POST /api/conversations/{id}/messages`，无 `continuous-episode.json` 记 engine_missing。否：CLI ask / live_probe（不经判官）。
- 选：**冷却下不跑题**——探不通即中止 rc=4，编排层等网关后 `--resume` 续跑（只搬干净完成题）。否：跑完打 `quota_tainted` 标——16:04 首跑实测 25/30 题成配额读数，垃圾还写进评测用户台账。
- 选：臂标签 = sidecar `runtime.source_revision`；产物落 `~/.finance-runtime/capability-benchmark-00/runs/`（仓内 runs/ 会把被测树弄脏，续跑 preflight 拒）。否：拿工作树 HEAD 现算 + 落仓内（首跑两个坑都踩了）。
- 选：费用只记 token。否：折算金额（仓内无 cost 埋点）。

## 当前状态（2026-09-10 13:3x）
`cdb16985`（基线 `gitea/main@5eb24515`），树干净。**29/30 已有干净读数**：25 道 09-09 晚在 8080 干净完成 + counter-h1/continue-h1/method-h1 三道 09-10 午在 57244 干净完成（round3 artifact `20260910T045031Z`）；chain-01/02 = 路由层 engine_missing（B7 定性，待重记）；**只剩 method-01**——三轮终局 LLM 5xx/429 连败（出口不稳非能力）。当前 terra 冷却至 ~15:36（round4 探针拦下，rc=4 零污染，B4 机制教科书级生效）。**09-10 起出口已切回 57244**（8080 整夜未愈；B8）：sidecar 8813 以备份 launcher 重起于 `cdb16985`（key 走 keychain、判官 override 保持、health 三读干净），臂标签沿用 `baseline-372d047c0b0f`（372d047c→cdb16985 只动评测侧，被测 runtime 零改动）。编排脚本已停（它固化 8080 env）；resume 由人工逐轮驱动：`run --resume <最新 artifact>`（命令形状见 blocked B8）。~15:36 后 round5 补 method-01 + chain-01/02；干净后写 `last-baseline-artifact.txt` 唤醒 watcher（PID 6909 仍在）自动收尾。

**两个新根因（都已处置，详见 blocked/00.md B4/B5）**：
1. B4：配额窗 ≈1.27M tokens 烧穿即 ≈4.7h 冷却；runner 原「gave_up 照跑打标」改为「不跑即中止 + resume」（`7180460d`，16 单测）。首跑废件归档 `~/.finance-runtime/capability-benchmark-00/runs/*.quota-tainted.json`。
2. B5：**判官二进制 grok-1.0.5 被 grok 自动更新清掉**（launcher 钉死绝对路径）→ 判官 FileNotFoundError → `judge_status=unavailable`。**生产 8792 在岗进程同样坏着**（本单不代改；已建议用户改 launcher 后 kickstart）。sidecar 已覆写 `LLM_JUDGE_GROK_BIN=~/.grok/bin/grok`+`SANDBOX=off`（偏离生产 env 两点，验收文须注明）。证据 episode 在 `evidence-20260909/`。

## 已验证
- `validate` / `overlap` / `seal-verify` rc=0；`test_capability_benchmark.py` **16 passed**（新增：冷却中止不跑题、题中烧穿打标、resume 搬运与互斥）；ruff 0；pre-commit 11 道过。
- sidecar health 三读（注意字段在 `runtime` 下、且是 create_app 冻结快照）：`source_revision=7180460d…` / `source_dirty=false` / `code_matches_repo=true`；`/api/llm/config ready=true model=gpt-5.6-sol`；判官 env 落进 `sidecar-env-8813.txt`。
- 编排循环已实测走到「等冷却」分支并存活（arm=baseline-7180460d8cfe）。

## 未验证 / 已知边界
- 30 题干净基线：**未产生**（等冷却）。产出后：`review-pack --decoy` → 人工评审（≥20% 双评）→ `aggregate`（decoy 胜则非零）→ 写 `docs/verification/2026-09-09-capability-benchmark-00-baseline.md`，并把干净终件拷回仓内 runs/ 提交。
- engine_missing 4 题（chain-01/02、continue-01/h1）出现在废跑里，冷却污染下无法定性；干净跑若复现才立案查门/路由。
- readiness `market_data_consistency=false`（快照 09-08 领先库 09-07），生产同态，只记录。
- 编排/sidecar 仍可能被低内存杀（B3 二次发作过）：恢复顺序见 blocked/00.md B3（sidecar 换 revision 重起时删 `baseline-chain.txt` 防混臂，脚本会 exit 7 拒绝）。
- 单跑不做显著性宣称（30×15 才分辨 5pp）；无同题 Knevo 样本不报竞品胜负。
