Spec **FAIL**：1 项 P1、1 项 P2。仅审 `6b70e54034b0fab736430d7e3d00d6f4f7fd617a...a7f5cc06c087c2d9db896450bb6033851e8e5789`；候选开头与结尾均 clean。没有读取 Standards 报告、修改候选源码或生产、调用真实模型、推送或合并。

- **[P1] 新快照把现有“截止外资料说明”路径变成保存失败。** 计划第 28 行要求“完整私有AgentEvidence……截止……预取在首次检查点、修复保旧追加新”，没有要求改变工具结果准入。`evidence_ledger.py:230–232` 要求全部 presented atom 都已进入事实账，但 `research_tool_registry.py:1338–1366` 原有“全晚于问句日，标注后交付”返回的原件会被事实账拒收；`agent_episode.py:512–525` 因而将普通领域边界升级为存储故障。独立实跑显式 cutoff=2026-07-24、资料=07-25：临时模式抛 `ValueError`；持久模式 `failed/storage_failed`、整树 fence、下一次模型未执行（1 次调用），丢失本应继续给出的日期解释。完整 `git archive 6b70e540` 同脚本两格均 `partial/model_finish`、2 次调用；混合截止内/外正常对照在两版都通过。见 [脚本](probe_future_evidence.py)、[候选原件](future-evidence-candidate.log)、[基线原件](future-evidence-base.log)。修复须区分“可告知模型的说明原件”和“可绑定结论的事实证据”，保留原件/日期语义和 E 号合同；不能删除截止、身份或共享 fence 守卫求绿。

- **[P2] API 夹具仍漏排空已触发的超时回调。** 需求明确“API测试结束要 drain 已启动后台工作”。新 `intelligence/tests/fixtures/run_supervisor.py:18–21` 只 join 线程池；`RunSupervisor.shutdown()` 的 `Timer.cancel()` 无法停下已进入 `_expire` 的回调，`_forget` 还会先移除它。独立探针用真实 `threading.Timer`、事件栅栏把回调停在实际 `claim_failed_run` 后：夹具已退出、executor 活跃数 0，Timer 仍 alive；撤销 monkeypatch 后才继续，并观察到已恢复的 users 环境。见 [脚本](probe_api_timer.py)、[原件](api-timer-candidate.log)。这是测试生命周期实现不完整；应在测试侧保留并等待已启动定时回调，不改生产关闭/auth/quota 规则，也不加睡眠。

独立所选回归 **80P**（证据 75、API 生命周期 3、关联恢复 2），未覆盖上述两形状。[原始输出](selected.log)；两关联恢复案例在当前 context/registry 校验通过后确实落到关联树拒绝，未由授权错误遮蔽。

旧工程证据身份核验通过：[机器核验](old-receipt-verification.json)、[Python 七项核验](old-python-receipt-check.log)。11766P/81S/2X、前端107P、E2E34P/2S 属固定 a7 的旧全叶；新18证据+4夹具、旧13/14/7/17/22变异的源/还原哈希、失败/还原执行数一致。不与本轮80P相加；这些工程绿数不抵消反例。没有评恢复 driver、跨进程租约或自然产品质量。

复跑命令见 [reproduce.md](reproduce.md)。本轴仅用 `code-review` Spec 流程、Git、指定 venv、离线脚本及 pytest；下一步是独立补丁树修复后原断言复验。
