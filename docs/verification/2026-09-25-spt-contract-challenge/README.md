# SPT 条件合同复核：拒收并隔离

## 结论

上一轮词面合同不适合作为视角判定器，**候选拒收**。三道原题通过的旧结果仍成立，但不能据此批准这套实现。用户的风险/机会观察/边界立场不改；被否决的是实现，不是通过改金标消掉失败。

这是同一执行者的反例复核，不是外部独立审查、盲测或未见题泛化评估。未新增模型请求、未写真实画像/考卷、未合入/部署。

## 先冻结再运行

`challenges.json` 在 `8ca4dc4c3a40374e2fa662695cd623107f35c90d` 冻结，随后对原匹配器运行。绑定上一轮原始 `candidate.json` 内容指纹，题目为新写的合成事实，不保存私人原文或画像。

结果：12项中4项符合预期、8项失败。原始结果 `baseline.json` 精确绑定8ca，来源是直接调用当时 `perspective_signals.matches`，没有修改期待值求绿。

| 失败类型 | 数量 | 具体问题 |
|---|---:|---|
| 条件被拼接 | 2 | 甲板块的容量/修复与乙板块的主动性混用；去年与今年的条件混用 |
| 未成立的信息被当事实 | 2 | 待核实信息、条件清单被当已观察事实 |
| 指代否定/撤回漏识别 | 2 | 后一句“上述内容不属实”或“这些观察已经撤回”没有使前句失效 |
| 过度拒绝 | 2 | 对明天的不确定性挡掉今天已知观察；给术语加引号挡掉真实观察 |

正反对照4项为：单主体正例、局部否定、无关方向的否定、不同完整句子的条件不拼接。它们通过不抵消上述错误。

## 修复范围

- 撤下本分支新增的条件匹配运行时接线。`evaluate_role` 恢复既有 `_hit_terms` 路径；新增护栏：出现 `signal_match_rules` 即报错，避免实验字段被忽略后假装验收。
- `_save_profile` 同样在任何写入前拒绝该字段，包括空列表、`None` 及显式 `allow_regression=True`，后者只允许旧画像回退，不授予实验权限。
- 实验源码移出 `intelligence/services` 到 `scripts/perspective_signal_candidate.py`，保留原匹配逻辑供复现；产品代码不导入它。
- 预演只对原画像与拟议边界调用正式评分器。实验仅报告 `candidate_literal_matches`，不再生成 `with_proposed_rules_and_boundary_in_memory` 的3/3判定；`candidate_disposition=REJECTED`、`candidate_runtime_enabled=false`。
- 新增 `--challenge-set`，复核候选哈希/目标、逐例期待及输入未变；反例失败使整体 `FAIL/exit 1`，不能被原题通过覆盖。即使另换一组全过的挑战也仍拒收、BLOCKED，不能自动恢复实验资格。

不继续堆否定词或板块名正则：那些补丁只会记住本次反例，无法提供主体、时点、已观察/待核实、撤回状态的保证。后续若要程序推断规则前提，必须先有带证据的结构化观察及明确归属；自然语言应用效果仍走真实模型问答验收。此处不再新增第二套语义判官。

## 固定版本验证

隔离实现冻结 `fa82a73cadb784ba2cb457d8384bb56a549ef0f6` 后，真实只读重放为 `FAIL/exit 1`：12项挑战仍4P/8F，候选 `REJECTED`、运行时未启用；原画像1/3、仅内存边界2/3。源文件/画像/manifest/patch/原题/候选/挑战前后指纹不变，正式卷仍缺。详见 `preview.json`，不复用旧3/3当新判定。

干净同SHA、17文件定向回归636P/0F/0S，无筛选，见 `clean-targeted-receipt.json`；全仓Ruff及提交钩子通过。进程内撤掉拒绝护栏，评分/考卷/合议/保存路径21F、旧画像控制5P；恢复后636P，见 `mutation.json`。测试绿色认证的是隔离与回归，不把已知实验错误改判为正确。不是全量Python/前端/E2E发布门禁。

01:43:09+08:00只读就绪HTTP503，缺`market_data_consistency`；本次检索协议通过，不解释历史间歇失败。相邻发布仍数据HOLD。生产写入、模型问答质量和独立审查均未完成，未借本次推进扩大权限。

## 重放

在审计树运行，预期退出码1（挑战失败）：

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python scripts/preview_perspective_exam.py \
  --users-root /Users/a77/.local/share/finance-workbench/users --user linxiaoqi5111 \
  --proposal docs/verification/2026-09-25-spt-exam-proposal/proposal.json \
  --match-candidate docs/verification/2026-09-25-spt-signal-contract/candidate.json \
  --challenge-set docs/verification/2026-09-25-spt-contract-challenge/challenges.json
```

只读预演不会写正式卷；旧画像评分限制不被本轮修复，原画像仍不能因此通过SPT验收。代码隔离测试通过与实验语义失败必须分账，不将两者合成一个“全绿”。
