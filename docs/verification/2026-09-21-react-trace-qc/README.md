# #809 质检返修的可复算证据（#832）

最终代码 `ec246761eec6caeac17ea9ad3477b06248f200f5`，原交付 `ac3bbd310`，中间修复 `a412a56aa`。本目录保存小型原件与日志；完整JUnit、首轮失败夹具、大模型事件流保留在外部根 `~/.finance-runtime/reviews/react-trace-qc-20260921/`，由 `EXTERNAL-SHA256SUMS` 绑定。

## 分母与归属

- `seams-before.log.txt`：最初独立27例，修前22F/5P。
- `mutations-a412.json`：27例基线绿，七项内存撤保护均被断言捕获。
- `local-adverbs-before.log.txt`：作者接着K3未完成探针扩大句内时间词反例，8F/3P；`local_adverbs_before.py.txt` 保留当时原期望。分号案例原期望逗号，正式回归保留原分号，不能把那份原探针全部转绿当验收目标。
- `mutations-ec246.json`：正式37例，九项独立撤保护各见行为断言红，collection errors=0；包含真实修复出口。
- `ec246-clean-focused.log.txt` / `receipt-ec246-focused.json`：最终代码相关369P。
- `a412-full.log.txt` / `receipt-a412-full.json` / `a412-full-execution.json`：中间版本完整12544P/87S/2X、首尾clean；**不能移签ec246**。
- `ec246-full.log.txt` / `receipt-ec246-full.json` / `ec246-full-execution.json`：最终代码全量12554P/87S/2X，首尾同SHA/clean；严格收据校验exit0，见 `receipt-check-ec246.log.txt`。不认证后来的main合流。
- `frontend-ec246/`：最终代码前端6步骤、110P/E2E34P2S、首尾身份和每条日志哈希。
- `ec246-checks.json`：全仓Ruff及registry四项+ledger crosswalk共六条命令全部0。
- `first-full-failed.log.txt`：首次全量失败原样保留（2F/14errors），定向复跑日志不是它的替代收据。
- `frontend-first-identity-rejection.json`：启动时SHA填错，测试前被挡，非前端测试失败。

## 独立复核不是绿色

`k3/execution.json` 记固定a412、600秒超时exit143，无REPORT。K3跑过274条现有测试，但自造探针第一次执行导入失败，随后上游504。`k3/events.compact.jsonl` 保留工具调用/结果与错误，抽取规则和原流指纹见 `events-manifest.json`。

`k3/root-qc.md`、`root_adapted.py.txt` 和相关日志均为**作者侧诊断**，不是K3报告/新独立验收。原探针缺PYTHONPATH、误用metadata/raw_refs/status/函数参数，以及管道掩盖rc的问题均保留。harness曾发出auto_retry_start，不能写成“全链零重试”；外层没有另启会话。

## 真实原件回放不是自然模型运行

`history-original-replay.json` 证明225行绝对页号/特征/原件不变，本次不验证跨工具hash稳定性；`condition-original-replay.json` 证明索引14/15删除后的计数清理，其他句子未改。两者 `natural_model_calls=0`，不翻转原金融质量not_passed。最终ec246的再次回放见 `ec246-history-artifact-replay.json`、`ec246-condition-artifact-replay.json`；对应脚本以 `.py.txt` 保存。

## 复算

使用仓库指定 `.venv-workbench/bin/python`，在固定ec246检出内运行：

```text
python -m pytest -q intelligence/tests/test_condition_reference_seams.py
python <复制出的mutate_seams_v2.py> <固定ec246代码根> <新的树外输出目录>
```

脚本副本 `.py.txt` 是防止被误当正式模块收集的审计附件；还原后可运行。变异只在独立子进程内编译修改后的源码，不写被测文件。旧S1/S2/S4探针复跑在 `legacy-probes/`，S1需当前合同API适配，原AttributeError日志保留。探针/变异不能替代新集成候选的完整门禁与独立批准。
