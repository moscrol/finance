# 在途交接 · cursor/perspective-lab-learning-loop-cd77

更新：2026-08-13 · PR #320 draft · **未合 main**

## 这个分支做什么

Perspective Lab：文章→结构化画像的学习闭环 + 视角运行时补强 + 蒸馏 skill。

## 当前状态

代码停在 `994f756e`。本交接单独提交。6 个功能 commit + 本文件。未合 main。
Mac 主仓脏，生产代码在 worktree `/Users/a77/.finance-runtime/fwp-perspective-learn`；
canonical 用户空间 `FORESIGHT_USERS_DIR` → `~/agent-memory/.foresight/<user>/perspectives/`。

sptfei 已蒸馏（20 approve / 2 reject），画像 `known_gaps` 待用户复核。

## 未验证 / 已知边界

- 真链路第 3 轮被 DuckDB **写锁** + 检索缓存旧窗口 + composer **模板降级**干扰；
  composer 正常执行时视角注入**未验到**。
- 缓存 key 无代码版本，修完同 query 可能吃旧缓存。
- `PERSPECTIVE_MANDATORY` 只在 `ASK_PLANNER_MODE=llm` 生效；默认 rules
  靠 `midterm_intent_for` 放宽 D6。
- 通用研究「公告/订单」契约 vs SPT 盘面派：本 PR 是加权重，不是改契约。
- `skills.registry.json` 在 main 上另有 12 处滞后（别人改了 SKILL.md 没重扫），
  本分支只并入新条目。VM 只有金融仓，**禁全量 scan**（会挤掉 kb 53 条）。

## 下一步

1. **合 main 等用户点头。**
2. 写锁释放后，生产 Workbench 单视角 sptfei 问同一句：D6 应有「房地产」，
   正文应有 SPT 证据层级语言（非确定性模板）。
3. Mac 三仓在场时 `python3 scripts/build_registry.py scan` 收敛注册表滞后。
4. 用户复核 sptfei 画像；再喂文章走 `perspective-distill` skill。

## 踩过的坑

- 宽松匹配无停用词：「分析/行情」误配板块名，挤掉「房地产」（已修，脏夹具锁死）。
- 修复轮不带视角会把 SPT 话术洗回通用口径（已修）。
- 引文核验无最短长度，「复盘」也能过（已修，≥6 字）。
- DuckDB 单写者；脏树另开 worktree；exec 长命令 Cloudflare ~100s 会 502。

## 已验证

相关回归 239 passed（`9c236c05` 后：learning/lab/midterm/planner/repair/compose）。
skill frontmatter/registry hash/双视图软链一致。停用词现解析
`['AI应用','AI硬件','商业地产','房地产']`，不再含「行业分析」。
