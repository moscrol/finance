Spec **FAIL：保留 1 项 P1 日期兼容残项；原 Timer P2 已关闭。**

固定范围 `a7f5cc06c087c2d9db896450bb6033851e8e5789...56d6062e4544ae40d2e91c19968f4bfe8066e60c`，实现为 7199db11、7c3b36b4；开头与结尾 clean。仅按已批准的有限设计复核，没有扩大 driver 或质量范围。

- **[P1] 全未来资料路径在上游已识别的完整日期形式下仍失败。** 当前要求“合法完整日期/时间表达若先被 registry 认作 cutoff 外，不能又在 snapshot 端误判不可解析”。`intelligence/services/episode_evidence.py:143–150` 直接调用 `date/datetime.fromisoformat`，与上游 `closed_loop_retrieval.py:372–392` 的既有日期合同不一致。固定 cutoff=2026-07-24，`2026-7-25`、`2026-7-25 09:30:00`、` 2026-07-25 ` 都被上游解析为 2026-07-25，工具返回 `future_of_cutoff`；快照却拒绝。真实本地 runtime 三种×两模式 **6 格失败**：ephemeral 抛 ValueError；durable 返回 failed/storage_failed、空稿，均只有 1 次模型调用。标准 ISO、紧凑日期、标准时区时间的 **6 格对照正常**。修复应按完整表达统一已支持的解析口径，保留未知/无效日期拒绝、截止与原件身份守卫，不能用任意文本中搜到日期来放行。

原反例复跑：未改输入的 future 脚本 **4 格正常**；mixed 脚本逐 JSON **2 格正常**，同 links 与请求级异 links 都 durable/model_finish、父/子各 2 次调用，没有仅凭 exit 0 判绿。脚本来源及哈希见 `copied-probes.json`，输出为 `original-future.log` 与 `recheck-mixed-duplicate-results.json`。

独立合同 **28P**：v2 精确展示与顺序、首写 atom/owner/targets/coverage 保持、未来展示恢复后不得入账/覆盖、全部非 links 字段重签替换拒绝、schema/digest/重复/资格篡改拒绝、从真实旧 v1 state 原件回读保留版本与摘要。真实 Timer 停在 `claim_failed_run` 后、已从任务表移除；异线程 teardown 在 release 前等待，release 后回调仍见 fixture 环境，并未等待另一 supervisor 的 Timer。见 `test_spec_contracts.py`、`independent-contracts.log/xml`。

保留守卫定向 **21P**（已在收到“停止扩大”前启动并完成）：缺快照/截止漂移拒绝且零补写、编码失败共享 fence、关联父子恢复拒绝、三个 API 夹具生命周期。见 `retained-guards.log/xml`。不与作者348P或旧全量相加；未运行全仓门禁、真实模型或跨进程恢复。候选、原证据、生产均未修改。

复跑唯一残项：

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python /Users/a77/.finance-runtime/reviews/research-closeout-20260920/runtime-evidence-recheck/spec/probe_date_forms.py /Users/a77/fwp-wt-runtime-evidence-closeout-0920
```

当前退出 1，完整结果见 `date-forms-results.json`。下一步只修该解析残项，以原日期矩阵和最小相邻守卫复验后进入 Quality。工具：code-review Spec 流程、Git、指定 venv、离线脚本与 pytest。
