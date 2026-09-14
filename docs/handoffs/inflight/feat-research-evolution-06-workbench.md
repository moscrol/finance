# feat/research-evolution-06-workbench 在途交接

最近更新：2026-09-14 · 06 HEAD `c5359120`（含 X1/X2/Y1/Y2）· 等第九轮 QC 复审，未合未部署

## 当前状态

1. **第八轮返修已收口**：Y1（源消息落盘前取消误折 B）/ Y2（读取失败激活矛盾链接）修复完成。
   根因：同一 `None` 表达「确认无来源/未就绪/读取失败」。修法：来源身份三态 +
   消息 API `create_run` 落 `maintenance_launch`（发布前可信启动身份）+ 新错误码
   `ERR_SOURCE_UNAVAILABLE`(503)。证据 `docs/verification/re06-fdb5f91d/REWORK.md`，
   决策快照 `docs/handoffs/2026-09-14-re06-round8-y1-y2.md`。
2. **Q2 过渡合同仍待用户明确接受**（第七轮遗留）：复核完成不再自动收尾，面板「确认成果」
   显式闭环。
3. **合并候选 `0bd11ece` 已过时**（= 06@7abaa938 + main@1fef3d27，不含 Y1/Y2）——
   复审放行后在 `c5359120` 之上重建候选并重跑门禁（树 `/Users/a77/fwp-wt-merge-re06`）。

## 验证（全部在干净候选 `c5359120`，dirty=false）

- Y1/Y2 探针 2/2 原样（中立目录回放 + 仓内收编 `docs/verification/re06-fdb5f91d/`）。
- 组合 145 = 历史 139 + 本轮 6（4 Y 镜像 + round8 收编 2）。
- 全量 **10147 passed / 0 failed / 77 skipped / 2 xfailed**，收据
  `~/.finance-runtime/test-receipts/20260914T083228Z-c5359120.json`。
- e2e 31/2sk；ruff 绿；pre-commit 11 道全过；前端零改动（run 载荷多 `maintenance_launch`
  键，前端结构类型容忍额外键，e2e 真后端集成已覆盖）。

## 合同要点（别再翻案）

- 来源身份三态是消费侧合同：confirmed_none 才可按登记归属消费；unavailable 一律
  pending + 503，不折算成裸 run；「未就绪」由创建时落身份消除。
- 接受侧保持乐观：窗口期抢登 200 是 R7 合法延伸（探针 setup 断言），收口只在终态闸。
- X1 自动认领已整体移除；矛盾链接只留审计不驱动状态；`fold_run_terminal` 吞业务拒收。
- 验绿陷阱：从审查树跑探针会被 conftest 劫持 import 到未修代码——拷中立目录跑。

## 未验证 / 已知边界

- product_verified 部分：I13 真人试点、I15 真实前向实验缺授权；I14 普通工程待验。
- field_evidence 无。e2e 绑定 spec 的 tablet/mobile 按设计跳过。
- 本修复前创建的 run 无记录身份：窗口期退回消息坐标核验（生产无此存量——未部署）。

## 下一步

- 第九轮 QC 复审 → 用户接受 Q2 + 放行 → 重建合并候选（c5359120 + main）→ 门禁 → 合 main
  （等用户确认）；push / 部署 / /api/health 验收单独授权。

## 踩过的坑

- 新 worktree 无 venv 与 node_modules：pytest 用主树解释器；e2e 加
  `WORKBENCH_PYTHON=<主树>/.venv-workbench/bin/python`；前端先 `pnpm install --frozen-lockfile`。
- `EvolutionStore.list_run_links()` 不收 run_id 参数，自己 filter。
- 动作错误体 `{code,message,detail}`：reason_code 在嵌套 `detail.detail`。
