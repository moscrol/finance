# feat/cap07-method-flywheel · 2026-09-09 晚 · 已完结：验收通过（带边界）＋ 生产已激活

## 最终状态（四项报告）

已实现 ✔ / 已进默认入口 ✔ / **真实验收 ✔（带边界）** / **生产生效 ✔（register+history 已做）**。
PR #692 合入 `794cc3e5`；验收与生产激活全记录在
`docs/verification/2026-09-09-method-flywheel-cap07.md`（判据对照、失败面 10 run 留档）与
`…/2026-09-09-capability-upgrade/progress/07.md` 尾段。

- 题 1 通过：`run_20260909_190926_670853`（模型轮零错误，`memory_lookup`×2，episode 原件含「方法验证
  读数」，判官通过，回答区分历史演练/说明降级/拒绝排序）。
- 题 2 语义通过：`run_20260909_191437_053778`（「上次方法的降级结论仍成立——只能提示观察」；会话上下文
  接力，本轮未再调工具、两次 502，边界已记）。
- 生产激活：生产 8792 已是含本单的 main；生产用户目录 register（前向起点 09-10）＋ history（payload 与
  验收深比较一致）＋摘要刷新；生产侧 `probe_tool.py memory_lookup` 0.03s 出读数。

## 接手人要做的（按日期）

1. **09-10 收盘、daily-full 落库后**：`cd <main 树> && .venv-workbench/bin/python scripts/method_validation.py daily
   --study-dir /Users/a77/.local/share/finance-workbench/users/linxiaoqi5111/method_validation/475597e2…5a2f
   --labels-db db/history_labels.duckdb --db-path db/market_feature_store.duckdb --user linxiaoqi5111`
   → 首个真实前向观察登记（有信号且阶段适用才登记 checkpoint）。
2. **09-17 前后**：再跑一次 `daily` 或等既有 03:50 夜间回检结算（旁路库未重建时 resolver 只 unverifiable
   并写清要跑什么）。
3. `daily` 接夜跑日程仍未安装（blocked #3，沿原任务授权，装前先看 checkpoint-recheck-mac-setup）。

## 当晚环境事实（不是本单代码缺陷，但会再咬人）

- **判官二进制**：`LLM_JUDGE_GROK_BIN` 钉带版本号下载件会被 grok 自动更新清掉 → 全部回答降级「未完成
  独立复核」。永远用 `~/.grok/bin/grok` 符号链接（agent-memory 已有同形卡）。生产已随 19:0x 重新部署修复。
- **Mirasim 写手网关（127.0.0.1:8080）**：闪断循环（首请求 502 → 熔断瞬时 503，窗口 1–4.5 分钟）；key
  会随生产重启轮换——侧实例起动时从 8792 进程环境现抄 key（`~/.finance-runtime/cap07-acceptance/
  start-cap07-workbench.sh` 已是此形状），不落盘不打印。
- episode / report.json 晚于 run 状态落盘：验收判定读磁盘原件事后验尸，不信驱动脚本即时打点。

## 现场清理

8807 验收实例已停；`fwp-wt-cap07-method-flywheel` 工作树与本地分支已删（合并完的分支直接删）。验收
产物保留：`~/.finance-runtime/cap07-acceptance/`（驱动日志）与 `~/.finance-runtime/cap07-users/`（episode
原件）。生产判官/网关如再出「未完成独立复核」批量降级，先查 `semantic_verifier.exc_class`。
