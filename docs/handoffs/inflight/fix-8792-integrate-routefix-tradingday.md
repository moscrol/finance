# fix/8792-integrate-routefix-tradingday：8792 版本对齐 + T2/T3 复验（已完结）

## 这个分支做什么
把材料路由修复（长度闸）+ 探针 ID 配对 + 交易日判定（#52）合进主干，验收后部署 8792，
固定参赛版本，并完成 T2→T3 揭盲后复验、补 09-11 L2 top100/quant。

## 决策与被否方案
| 选了 | 否了 | 理由 |
|---|---|---|
| 两分支 merge --no-ff 进 main（2ee664fa）再部署 | 只部署路由修复最小面 | 用户拍板「与主干合并后部署」；交易日修复同车 |
| 新快照 worktree + 移 symlink + deploy 脚本 | rsync 盖旧快照 | 旧快照留作回滚锚；R-06 要求 source_dirty=false |
| 弃权/失败轮直接重试（T2 第 2 次、T3 第 3 次成功） | 当场改 50s 自审预算 | 失败样本先归档（TimeoutError/502 同族），改 runtime 需另行设计 |
| L2 跑 canonical 管道 run_l2_pipeline.sh | 手搓 SQL 补行 | 写入只走既有管道；幂等 DELETE+INSERT，ops 台账自动记 |

## 当前状态
全部完成且已推 gitea/main=3ca03d8d（代码 2ee664fa + 归档文档）。生产 8792 运行
2ee664fa（快照 finance-workspace-2ee664fae9c4，指纹一致、不脏）。Grok 判官仍撤（启动器四行注释未动），
K3 自审在环。复验结果与新缺口：`docs/learning/knevo-distill/recheck/2026-09-12-t23-nogrok/RESULTS-2026-09-13.md`。
决策快照：`docs/handoffs/2026-09-13-8792-integrate-deploy-recheck.md`。

## 已验证
- 集成树全量 pytest 9540 passed / 0 failed；ruff 全绿（两合并各自无冲突）。
- 健康：source_revision=2ee664fae9c4、code_matches_repo=true；进程无 LLM_JUDGE_*。
- 小样检索题 + T2 + T3 三轮实质答卷：llm.used=true、judge_status=repaired（K3 自审在环）。
- T3 逐条命中 K01/K02/K04/K05（详见 RESULTS）；Knevo 两个实测错误均未犯。
- 09-11 L2：limitup=33 / top100=100 / quant=37 全 complete、值全非空；行情三表非空抽查过。

## 未验证 / 已知边界
- 自审长上下文不稳：5 次尝试 3 次 judge_unavailable（TimeoutError/502），嫌疑 50s 预算
  + 网关 502 抖动；未修，无环境旋钮（episode_semantic_verifier.py:118）。
- T3 有效答卷的会话含两次失败存根，非纯净上下文；正式 PK 必须全新会话 + 未见新题。
- 题材流 fact_theme_flow_daily 仍停 09-02（主树有他人在途改 sync 脚本，未碰）。
- hithink 重建版 09-11（5553 行 + 302132 + 派生）待 QC 复审 + 用户授权才换库；生产现为 5552 行旧补。
- 第 1 轮真实盘面题未复验（Knevo 该轮引用截止后收评，留作反例）。

## 下一步
1. 出未见新材料题 → 全新会话正式 PK（用户侧备题；先冻结 8792 原答再揭盲）。
2. 自审预算缺口：设计旋钮化/提预算/重试策略，拿 RESULTS 里的失败样本做验收。
3. hithink 换库走 QC 复审 → 用户授权；L2 闲鱼迁移收口（清单第 8 项）与工单 #50 仍未做。

## 踩过的坑
- 本 harness 每条 bash 都重置回主检出树：跨树操作必须逐条 `cd <树> &&` 或 `git -C`，
  本轮因此把全量 pytest 在主树（别人脏树）白跑了两次——读数前先看 pwd。
- `git commit -- <文件> -m "msg"` 会把 -m 当 pathspec；-m 必须放 `--` 前。
- 探针重试会在同一会话叠加失败存根；要纯净上下文就新开链重跑。
