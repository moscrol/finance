# fix/judge-recovery-01 · 判官修复 01

## 这个分支做什么
让已查到、有证据的答案能交付：契约外绑定不连坐核心答案；修复进展按内容算、来源独立性另记；纯语义缺口做一次有界回检索（V11）。合同 `docs/superpowers/plans/2026-09-09-capability-upgrade/01-judge-recovery-goal-brief.md`，进度 `…/progress/01.md`，范围外登记 `…/blocked/01.md`，决策快照 `docs/handoffs/2026-09-09-judge-recovery-01.md`。

## 决策与被否方案
- 契约外绑定分两档：哈希可核验→扩展区 STRIP_OK，池外/重复→仍 BLOCK。否「一律放行」（编造引用）与「一律 BLOCK」（复现二连坐）。
- 进展=新 id 指向未覆盖输出；家族另记 `new_source_families`。否「保留家族门」（同源补锚被拒）与「新 hash 即进展」（ARL-0014 f5）。
- V11 默认开 + `FINANCE_V11_GUIDED_RETRIEVE=0` 回滚。否设计稿默认关：合同点名「不能只接永远不开的开关」。
- 回检索走注册表 `kb_search` + `bounded_stage` 子窗；否直连 `kb_rag`（第二条检索链）。
- lifted 只记账；否绑进台账（V11 §10.1）与模型改写（V8 决定）。

## 当前状态
已提交 `c83cd0bf`（含第四轮验收记录），树干净。未合 main、未切 8792。基线 `gitea/main=5eb24515`。PR #693 正文已 PATCH 为实测结果。基线 worktree `/Users/a77/fwp-wt-judge01-base` 已移除，sidecar 已停。
**token-usage 叠加兼容已验（2026-09-10）**：container merge-tree（无冲突，exit 0）物化后全量 **8379 passed / 0 failed**（5.6 min），定向三组 241+191+49 全过，pre-commit/ruff/字段契约全绿。详见 progress/01.md「任务 2」。

## 已验证
直接测试文件 241 passed；V11 新测试 22 条；adapter/verifier/invariant 191；pre-commit 11 道过；`check_unread_fields` 无新增。全量安静跑 8330 passed / 0 failed（15.6 min；此前高负载跑 3 条超时看门狗测试红、单跑绿）。391 份真实存证：基线 vs 分支首个损失点 A/B 零差异，`extension_outputs` 出现 0 次。

## 未验证 / 已知边界
- **真实 Workbench 对照已跑完（第四轮，sub2api 8080）**：5 题 × 2 臂全草稿。判官可达时三刀按预期（Q1 两臂同形、Q5 分支拒「必涨停」前提给条件性研判）；Q3 证据量差（基线 171 vs 分支 13）归因 OpenAI-family 上游池间歇 503（51 账号全 503 failover），非判官误挡；Q4 分支单发 HTTP 400 待归因。「冻结样本整体挡回减半」本轮无法判定（4/5 题至少一臂判官不可用），需上游池稳定后重跑。
- V11 lifted 用户不可见（V8 后公开稿无存疑标）；§8 A/B 与台账 `R-20260822-05` 未做。
- 缺陷一自然频率不可从存证读出（被拒修复轮不落事件）。

## 下一步
1. ~~合并前以 `feat/judge-token-usage` 为准重跑本单测试。~~ **已完成（2026-09-10）**：叠加树全量 8379P/0F，三组定向 + 门禁全绿，可合。
2. 用户确认后合 main；TOOLKIT 登记 `judge_loss_point_replay.py` / `launch_workbench_sidecar.sh`（harness-reference 树脏未动）。
3. （可选，不阻塞合并）上游池稳定后重跑一轮真实验收，给「挡回减半」一个判定。**2026-09-10 第五轮已部分执行（cockpit 57244 出口）**：12:18 57244 连续 2×200、8080 仍 503 → 按 /tmp/k3-wrap-common.md §17 用 `WORKBENCH_LAUNCHER=…bak-20260909-pre-mirasim8080` 起 8821（基线 5eb24515）/8822（本分支）。踩了两个环境坑（见「踩过的坑」）：备份 launcher 钉的 grok-1.0.5 二进制已被自动更新清掉（FileNotFoundError），且 1.0.25 + `--sandbox read-only` 在 `/var/run/docker.sock` 符号链接上 fail-closed（GrokCliExit）——两项都用进程 env 覆盖修掉（`LLM_JUDGE_GROK_BIN=/Users/a77/.grok/bin/grok`、`LLM_JUDGE_GROK_SANDBOX=off`，必须在 source launcher **之后** export，nohup 直起 zsh -c）。修好后**分支臂金丝雀 Q1 拿到三刀全活的完整样本**：`structural=completed / judge=repaired / v11_triggered=True / v11_outcome=lifted / v11_lifted_count=2 / new_hit=6 / judge_unavailable=0`——判官标出 2 句问题（申菱环境无注册证据绑定、曙光数创北交所事实外部引入），V11 回检索补 6 条新证据后两句全部 lifted，公开稿交付。这是本分支三刀第一次在真实对话里端到端跑通。随后 Q2 分支臂 13:11 起连续 429（cockpit sol `model_cooldown`，`reset_seconds=8202` ≈ **15:29 重置**），基线臂 Q1/Q2 全被 429 打脏（2 条/0 条证据即回 gap 模板）。按 tag-and-continue 规则停批：13:05 后两臂 run 全部作废（存证仍在 runs 目录，不混入结论）；sidecar 已停。已排 15:33 唤醒续跑；基线树 `/Users/a77/fwp-wt-judge01-base`（5eb24515）保留备用。

**当日验收搁置（2026-09-10 17:20 定）**：15:33 / 16:07 / 16:41 / 17:19 四轮探测，57244 在 `auth_unavailable` ↔ `server_is_overloaded` 间交替，仅 16:41:26 单发一次 200、20s 后复探即回 overloaded，连续 2×200 全天只在 12:18–12:20 出现过一次（即第五轮那段，50 分钟后又被 cooldown 打断）；8080 全天 503。结论：上游池（ChatGPT 侧与 sub2api 侧同向）全天不稳定，「挡回减半」判定当日不可为。**已排 2026-09-11 09:47 一次性唤醒**续探；接手者若会话已死，按 progress/01.md「续跑命令」+ 本文件「踩过的坑」后四条（grok 符号链接 / sandbox=off / env 覆盖顺序 / 绝对路径）执行即可。剩余题面：基线臂 Q1–Q5、分支臂 Q2–Q5（分支 Q1 干净全活样本 `run_20260910_130521_431608` 已计入结论）。

## 踩过的坑
- `_judge()` 夹具第二次调用自动放行；issue 里「第N句」会被并回拒句集。
- 23 个 adapter 替身是严格签名，新 kwarg 按 `inspect.signature` 条件传。
- 两臂并发发题→全 429→网关端口消失；先探网关、单发、串行。
- **grok 下载目录会被自动更新清旧版本**：备份 launcher 钉死的 `~/.grok/downloads/grok-1.0.5-macos-aarch64` 已不存在（现存 1.0.24/1.0.25），进程 env 里必须改指 `~/.grok/bin/grok` 符号链接；判官不可用先查 `semantic_verifier.exc_class`，`FileNotFoundError` 就是这个形状。
- **grok 1.0.25 + `--sandbox read-only` 在本机 fail-closed**：`/var/run/docker.sock` 是符号链接，sandbox 解析不了就直接拒跑（`GrokCliExit`），sidecar 需 `LLM_JUDGE_GROK_SANDBOX=off`（生产 launcher 也是这么配的）。
- **env 覆盖必须在 source launcher 之后**：`zsh -c` 一次性包裹 + `nohup … &` 直起才行；先 export 再调脚本会被脚本内 source 重新盖掉（`ps eww` 验进程 env，别看自己的 shell）。
- **从别的树调相对路径 `scripts/launch_workbench_sidecar.sh` 会找不到文件**（后台命令 cwd 会复位）；一律用绝对路径。基线树 5eb24515 没有该脚本（新文件），用本分支树的脚本起基线臂即可。
