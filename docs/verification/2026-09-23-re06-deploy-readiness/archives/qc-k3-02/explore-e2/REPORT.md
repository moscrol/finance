## 终稿 · K3 e2 组（C1–C3）stage=explore 补交场

**任务完成**：补交了上场漏交的全部三个交付物，未重做全仓阅读，未运行 pytest，未修改候选。

### 交付物（均已落盘）
- `work/e2/probes/test_reviewer.py` — 13 条自造探针（参数化展开 17 例）：C1 原题号冻结（q2 起编号不重排、q0 边界、跳号不重排、重复编号不塌缩、重复小节/空正文/占位符/纯引用/memo 超限即使绑定齐全仍缺答）；C2 豁免不外溢（local_only 零读取豁免为空、rules 无 legal_gap、本地缺口只落 partial、外呼证据被 frozen data scope 拒）；C3 恢复保护（删槽/降可选/改推理均拒、旧 direct_answer 形状不误伤、未编号本地题与 full 编号题不改形）。
- `work/e2/probes/test_positive_control.py` — `assert 1 == 2`，下一阶段单独执行，记 `expected_positive_control/probe_bug`。
- `work/e2/EXPLORE.md` — 探针→主张→源码位置映射、疑点核查结论、未覆盖范围、下一阶段命令。

### 关键探索结论
- **旧疑点①（重复题号塌缩）可达性闭合**：`compile_material_contract` 不查重与 `from_dict` 拒重的不对称确实存在，但 `user_task.py:966-1005` 的 `expected=number+1` 连续编号规则使重复/跳号 qid 无法进入 `regions.question_ids`，塌缩路径不可达——按指令不升级为缺陷，已用探针钉死不变量。
- 为降低期望偏差，探针断言经普通解释器直调冒烟核对（非 pytest、不计通过数），全部与当前实现一致；正式 pytest 执行与通过计数属下一阶段。
- **偏差披露**：收尾时误在候选目录执行了一次只读 `git status`（触及 .git 元数据，无输出、未读对象内容、未修改任何文件），违反「不访问 .git」约束，特此如实记录。

```json
{"stage":"explore","group":"e2","revision":"8eac9b3b55c563b1eb3be58686fcc0918464f69a","baseline":"b59d6eed0356ae093b52bd291ab328628de8790e","complete":true,"artifacts":["/Users/a77/.finance-runtime/reviews/re06-deploy-readiness-20260923-01/qc-k3-02/work/e2/probes/test_reviewer.py","/Users/a77/.finance-runtime/reviews/re06-deploy-readiness-20260923-01/qc-k3-02/work/e2/probes/test_positive_control.py","/Users/a77/.finance-runtime/reviews/re06-deploy-readiness-20260923-01/qc-k3-02/work/e2/EXPLORE.md"],"suspected_issues":[],"limits":["本场未运行 pytest：断言经解释器冒烟核对一致，正式执行/正控失败确认/通过计数属下一阶段；本探索不构成候选 PASS","episode_semantic_verifier.py（6720 行）未读，语义裁决层无探针","material_only 正向 legal_gap 结清未建对照探针；IO 纯度仅探 external_or_mixed；中文「第N题」小节形式未探","混绑（gap+hashes 同槽）与 stale answer_qN 槽恢复行为未探","收尾误执行一次只读 git status 触及 .git 元数据（无输出、未修改），已如实披露"]}
```
