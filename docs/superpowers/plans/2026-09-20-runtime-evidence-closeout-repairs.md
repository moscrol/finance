# 运行恢复收尾：展示记录与事实账本分开保存

基线 `a7f5cc06c087c2d9db896450bb6033851e8e5789`。本轮独立 Spec/Standards 证明：原有全截止外资料提示、父子同哈希不同输出关联，两条合法运行在新增快照检查点变成保存失败；API 测试排空还漏掉已触发的 Timer。旧全量及变异通过不能抵消这些新反例。使用独占补丁树，subagent-driven-development 实施后 Spec → Quality；不合 main、不开放恢复 driver、不写生产。

## Task 1：保存实际展示，同时保留已接纳事实原件

事实账本的首写原件、来源日期、分支归属和覆盖关系保持不可替换；模型展示次序与展示用途是不同合同。仅用 presented_hashes 回查账本不足以表达已有合法输入。选择版本化记录实际展示，避免通过关闭保存守卫、偷偷删掉日期提示或覆盖首次原件来消除异常。

- [ ] 同解释器在原基线复跑独立 `runtime-evidence-review/spec/probe_future_evidence.py`、`standards/probe_mixed_duplicate.py`，保留原输入红证据。实际 GLMAgentRuntime/ContinuousAgentEpisode，脚本模型、假工具和临时存储即可。
- [ ] 快照保存账本原件与精确展示原件及顺序。已入账展示允许有限的请求级输出关联差异（supports/contradicts），但正文、来源、日期、结构化观察、血缘及其他字段仍逐项一致；不把不同正文的同哈希伪件放行。保留首次入账 targets/owner/coverage，不为展示自动扩充覆盖。
- [ ] 明确表示截止外展示：只有真实可解析日期晚于固定 information_cutoff 的资料才可作为此类展示，恢复后仍不进入可用事实账本或覆盖集合。保存实际日期提示文本，继续让模型说明“源有材料但日期不适用”。无截止、未知当前资料、无效日期及普通未入账原件继续拒绝；不以标题关键字作为授权依据。
- [ ] 采用严格版本化 schema，提供旧 v1 快照读取兼容。完整摘要覆盖实际展示及其分类；不静默丢字段，不仅比较哈希，不降低未知字段/缺字段/更改日期/更改观察值/重复身份/伪造覆盖的拒绝。既有 v1 记录读回不应偷偷改变其摘要或语义；必要时保留所读版本，只在新 capture 写新版本。
- [ ] restore 的 presented_evidence 必须等于原实际展示顺序和完整对象；恢复账本仍等于首次原件。混合批次、全未来/混合日期、临时/持久模式均可继续到父第二次模型调用，保存失败 fence 和恢复前授权/证据门保持。
- [ ] 在既有证据快照及实际 Episode 测试补承重反例：不同输出关联允许，改变正文/观察值仍拒绝；截止外展示恢复后不可用于 mark_output_covered；新旧版本、摘要篡改、关联子树与共享故障 fence。有限变异撤回关键检查/接线必须使对应断言失败。

## Task 2：API 测试退出时等待已触发的超时回调

- [ ] 基于独立 `spec/probe_api_timer.py` 的确定性停点，测试在真实 Timer 已进入超时回调、工作线程已空时发起 fixture teardown；teardown 必须等释放回调后才能结束，且回调仍观察到测试环境。
- [ ] 修复只改变测试夹具的排空责任。生产 shutdown 仍非阻塞，不改鉴权、配额、超时与回调效果。不可枚举并等待全进程线程；只跟踪此夹具创建/持有的超时回调，兼容已从 supervisor 内部任务表移除的 Timer，并规避自 join。
- [ ] 保留正常完成、排队取消、运行中假任务和超时结算的已有回归，确保临时目录/monkeypatch 恢复发生在最后一个测试自有回调之后。测试用同步事件而非靠 sleep 碰竞态。

## 交付

- [ ] 新树 `fix/runtime-evidence-closeout-0920`，Python 使用主树 `.venv-workbench/bin/python`，仅定向 Ruff/相关回归；不要在已有冻结树里写日志/缓存收据。全部证据进 `~/.finance-runtime/reviews/research-closeout-20260920/runtime-evidence-fix/`。
- [ ] 只用 pathspec 提交，两个任务可各一提交；自审、推送分支、≤3KB inflight 和必要日期快照。保留旧 6b70/a7 红绿证据和旧全量身份。
- [ ] 独立 Spec → Quality 后才安排全叶及当前 main 集成。此补丁不等于恢复 driver、跨进程租约、自然模型研究质量或生产上线已完成。
