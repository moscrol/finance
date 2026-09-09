# 历史发现研究：接手入口

## 这个分支做什么
事后发现特征→假设→历史同类/失败/条件全集比较；接既有Workbench，不另造loop。

## 当前状态（2026-09-09 下午）
树 `/Users/a77/fwp-wt-historical-discovery`，分支 `codex/feat-historical-discovery`，基线 `gitea/main@f90af450`（main 至今没动）。两处待修已修并提交：B `a963002f`（finish 放行合法 case 引用，资格仍只看 history_query 原件）、A `7751ab81`（空池回退先落 `application_tool_call` 声明，不再有孤儿 tool 消息；main 原有缺陷，可独立 cherry-pick）；另修分支原有门禁 `b24c43f3` / `f818e6cd`（历史三工具共享 finance_query 的注册表/切换板/标签/目录对齐）。全仓 CI：ruff 绿；pytest `f818e6cd` 8616P/3F，3F 为负载 40 时的时序抖动（单跑可过、回退对照排除因果），负载低时重跑取干净收据。

## 真实复验（8809 冻结库，并发 1，独立 agent 按 C1–C5 评分）
M1 90 / M2 100 / M3 80 / M4 80 / M5 100，全部 PASS 无硬伤；M2、M4 上一轮的 `history_unknown_result` 消失（B）；M5 真触发空池回退且后续四轮模型调用全成功（A）。M6 与 UI 追问撞上网关 `model_cooldown`（两个模型全部凭据冷却，reset 约 16:05），**尚未复验**。材料在 `R/rerun-20260909-b24c43f3/`（R 见下）。

## 下一步（接手先做）
1. 网关冷却后：`python3 /tmp/hd_rerun.py --skill-mode hybrid M6`，隔 ≥3 分钟再 `UI`（/tmp 已清则按实施交接末段重建：POST /api/conversations + /messages，skill_mode=hybrid，串行轮询）。审计 `scripts/audit_historical_research_artifacts.py <run目录>`，独立评分，写进 R 与实施交接；两题都过再勾计划 Task 6 第一项。
2. 起 8809 必须覆写 `LLM_JUDGE_GROK_BIN=/Users/a77/.grok/bin/grok`、`LLM_JUDGE_GROK_SANDBOX=off`（启动脚本里的 1.0.5 路径已失效；生产 8792 同样带着失效路径，改脚本/重启生产要用户确认）。
3. 合 main、切生产要用户确认；前端叶子未跑（分支未触 webapp，diff 为空）。

## 决策与被否方案
受限typed算子，未用任意SQL/新runtime；原件只经 RunStore。A 不伪造 model_turn、不只在发送边缘补消息；B 不删完整性门、不把草稿升级为事实。历史三工具保持共享 finance_query（spec 决定），装配读元数据声明而非改成三个新 capability。

## 未验证 / 已知边界
M6、UI 未过；runtime 对 429 无退避（0.6s 连打三次）；M3 一轮 backfill 修复事件不在 episode.events；S3 仅纯候选桥，S4 未建；L2/晚间卖方/晨汇 pending_sync。

## 踩过的坑
解释器用主树 `.venv-workbench/bin/python`。R=`/Users/a77/.finance-runtime/historical-discovery-20260909`。`run_status=completed` 不等于可评分：看 `semantic_verifier.exc_class` 与 `answer.md` 长度（160 字即降级）。发题留间隔，429 是限流不是能力结论。收据认 revision 时间戳文件。
