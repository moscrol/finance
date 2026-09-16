# docs/fengyuan-distill-0916

## 这个分支做什么
把风远94 对账台账（`docs/learning/knevo-distill/fengyuan94-corpus-dedup-2026-09-16.md` §5）判为「新增」的
优先 8 卡（R12 / R27 / R28 / R29 / R30 / R35 / R61 / R65）走 `perspective-distill` 第 1–4 步进 `fengyuan` 画像。
画像、原料、卡片、patch 全在 gitignore 的用户空间；本分支进 git 的只有本交接 + `evolution/backtest-queue.md`
Q-002 追加行 #12–#15（数字阈值排队，均未提交）。

## 当前状态（2026-09-16 15:35，接手自 pi 会话）
- 原料私存 `~/.local/share/finance-workbench/private-distillation/fengyuan-20260916/`（0700；148 文件 before 备份 +
  sha256；`plan.json` 记四批：优先 8 / 第二批 14（已切好 `batch2-20260712-new-rest.md`，7106 字，未 ingest）/
  「部分」22 未切 / B 侧 08-08 快照 11 条未切）。
- **步骤 1 ingest 已落**：article `pa-516facf90296`，date 2026-07-12（快照日），风远 21 篇；写前核过指纹 = 备份。
  8792 已由另一会话切到 gitea/main=0758a423，切后 GET /api/perspectives 仍见 fengyuan 21 篇（可见性闸通过）。
- **步骤 2 extract-cards 阻塞在模型网关**：127.0.0.1:8080 六模型自 14:50 起全 502/503（网关 /health ok、上游不可用），
  14:55–15:33 每分钟探针无一恢复。共享网关，不自行重启、不绕道别的凭证。
- 评审判据已写好：job 目录 `review-policy.md`。R27 / R29 / R30 与边界第 1 条「不做报表核查」交叉，
  **保持 pending 待用户拍板**，不批不拒；其余五张按三门评审后执行。
- 考卷基线：`perspective exam run` 3/3 通过（确定性，不用 LLM；边题正是「核三张报表质量」→ 批财报规则后必须重跑）。

## 下一步
1. 网关恢复后（先 `curl …/chat/completions` 见到 `choices`）：
   `FORESIGHT_USERS_DIR=/Users/a77/.local/share/finance-workbench/users FORESIGHT_USER=linxiaoqi5111 \
    .venv-workbench/bin/python -m intelligence.cli perspective extract-cards --user linxiaoqi5111 --perspective fengyuan --article-id pa-516facf90296`
   → `propose-patches` → 按 `review-policy.md` 逐条 `review-patch` → `exam run` → 覆写本交接。
2. 剥离数字若与 Q-002 #12–#15 不一致则改表；再决定是否提交本分支（handoff + backtest-queue 两个 pathspec）。
3. 第二批 ingest 用 `--date 2026-07-12`；B 侧用 `--date 2026-08-08`；每批 <16000 字。

## 踩过的坑
- 用户空间真值在启动器：`FORESIGHT_USERS_DIR=/Users/a77/.local/share/finance-workbench/users`、
  `FORESIGHT_USER=linxiaoqi5111`——skill 文档「别用 linxiaoqi5111」那段已过期，以启动器为准。
- 启动器 `PYTHONPATH` 指向 `finance-workspace-runtime`，整份 eval 进来会加载别的树；只取需要的几个 export。
- 提供方顺序：`LLM_API_KEY` 未设 → 走 `FORESIGHT_BUILTIN_LLM_*`（kimi-k3 经网关）。

## 未验证
- 尚无 patch 产出，approve/reject 清单为零。
