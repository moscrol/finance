# feat/research-evolution-06-workbench · 2026-09-13 · 研究进化 06：返修完成，等用户确认合并

## 这个分支做什么

01–05 接进既有 Workbench 会话（GET 投影 + actions/bindings/events + 前端「维护」页），06 只组装不改域算法，单 writer `EvolutionStore`。**QC 驳回的 13 条（S1–S3/R1–R10）已全部返修完**。

## 决策与被否方案

- R9 读不动：该绑定整条不进评估 + 模块 unknown + gap；否了「只喂基线给 assess」（会算出语义错误的 unchanged）。
- R7 关联闸：run 属本会话 / 禁折回原判断 / 判断 run 会话一致 / 事件时刻不早于请求；否了信任前端自报 run_id。
- R1 恢复：消息入口拒收 → `cancel_rejudge` 退回 open；否了挂假进行态。
- 绑定幂等：`binding_id` 是自然键（owner+对象+refs+entity+as_of，不含条件）；同键异载荷 409，绝不第二行。
- S1 测试：线程直调 `apply_action` 断言一胜一 409；否了 QC barrier 探针——验证进事务后它必死锁，是探针失效不是 bug。
- 错误码只增不改：新增 `run_binding_mismatch` / `invalid_transition`。

## 当前状态

- 全部已提交，树净：HEAD `15b36aeb`（docs）；代码 SHA `297c47c3`。
- 返修计划与探针复核：`docs/superpowers/plans/2026-09-13-research-evolution/06/REWORK.md`；证据表在 `PROGRESS.md` 返修节。
- 新台账 `run_links.jsonl`（重判请求↔run 关联）已登记 `docs/learning/ledger-map.md`。
- **未合并未部署**，等用户确认；合并顺序：规格分支 `docs/river-next-specs` 先进 main。

## 已验证

- 全仓 pytest：**10014 passed / 0 failed**，收据 `~/.finance-runtime/test-receipts/20260913T131404Z-297c47c3.json`（dirty=false，之后仅 docs 提交）；ruff clean。
- 06 套件 80 passed（含 17 返修合同测试 `test_research_evolution_rework.py`）。
- 前端 lint/typecheck/build 过；vitest 87 passed；e2e 研究进化 spec 三 project 15 passed、desktop 全量 10 passed。
- QC 四探针指向本树重跑全部「以新合同失败」= 旧病不再复现（细节见 REWORK.md 状态行）。

## 未验证 / 已知边界

- 练习反馈 UI 按 dict 原样渲染，没压过真实题包（04 生产题包没人签）。
- R3 观察器只接 Workbench RunStore，别的 run 链不在覆盖内。
- e2e 隔离服务无市场库，绑定→变化→复核整链只由 python 测试覆盖。
- 原批次未做项照旧：I13 真人试点 / I14 后台暂停 / I15 真实前向实验（BLOCKED §3）。

## 下一步

1. 用户确认 → 合并（规格分支先行），部署后只认 `/api/health` 的 revision。
2. QC 复审：重跑四探针（预期全红=修复成立）+ 看 `test_research_evolution_rework.py`。

## 踩过的坑

- 探针硬编码 QC 树路径：`standards_*.py` 要 sed 换 `REPO`；`spec_api_repro.py` 有 `--repo-root`；`root_probes.py` 跟 cwd 走。
- 本树无 `.venv-workbench`，e2e 必须带 `WORKBENCH_PYTHON=/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。
- 存量 mobile e2e 用例基线上就红（视口 1024 时开关按钮不出现却死等）——本次顺带修了，别当回归查。
