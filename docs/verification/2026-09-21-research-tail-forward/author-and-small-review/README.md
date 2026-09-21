# 前向整合工程证据与小片独立审核

此目录为冻结证据，不代表合主干或部署。来源根：`~/.finance-runtime/reviews/research-tail-integration-20260921/`。复制文件的来源、重命名和哈希见 `sources.json`；`.log`/脚本加 `.txt` 避免忽略规则或被误收集执行，内容逐字节不变。外层 `sha256-manifest.txt` 覆盖本目录除自身外所有文件，提交后用 `scripts/check_evidence_archive.py <本目录> --revision <提交>` 验完整 Git blob，不仅验磁盘。

## 作者工程（固定项目解释器 Python3.12.13）

| PR/固定源码 | Python全量 | 前端/E2E | 裁决边界 |
|---|---|---|---|
| #831 ea5c3a94618a15e37f914c8b1a13e271875e4337 | 12444P/87S/2X | 110P / 34P2S | 两项独立小片 |
| #833 7edfe24e76afbd5c365fbf97dd2414847b086f88 | 12631P/87S/2X | 110P / 34P2S | 历史分支组合 |
| #834 cb16cd463db5c19b3187a5137009791082874653 | 12870P/87S/2X | 110P / 34P2S | 运行时分支组合 |
| #835 d82cb16b5ef31d23339a1bef7084a0dcb8221e15 | 13305P/87S/2X | 118P / 34P2S | 财务分支组合 |

P=通过、S=跳过、X=预期失败。各 Python 收据 exit0，Ruff、四项 registry、crosswalk各0；crosswalk保留98条既有反向警告。操作员逐项校验结果见 `author-gates-verified.json`，含24份前端步骤日志哈希复核。解释器均 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，原日志与收据记录依赖指纹、净树和首尾SHA。

历史/运行时旧包装器 `*-main-gate.rc` 是 **1，不改写为0**。无效的收据目录变量使读写脱节，失败文本的UTF-8中文括号又被Bash并进变量名。pytest自己的精确收据exit0、条件校验通过；修复版显式收据回放exit0是另一动作，不冒称原包装器绿。新正式修复归#814，本目录的c35只为诊断。

## #831独立结论

`small-sol-review/report.md` 为一个 Codex/gpt-5.6-sol 独立session分Spec/Quality两节的原报告。原事件有105P/1S、Ruff0、离线独立probe最终PASS和turn.completed；不冒称双独立审核者。操作员收窄为 `PASS_WITH_LIMITS`，见 `small-sol-review/operator-qc.md`：探针没有独立压满结果上限、Timer已先release，强限额/挂起回调证据来自本次独立重跑的正式回归。首次probe自身SyntaxError与旧host/容量阻塞均保留。

外层未捕获原审进程exit码，不补造0；末次identity命令事件stdout为空，操作员随后回读同SHA/净树。无真实CRG后端动态验证，不签三领域代码或后来main#830。

## 门禁诊断中止

c35f61d37仅本地诊断候选；固定15P、六撤保护断言红，前端六步过。发现#814更完整实现后停第二路线，17:53对本轮pytest PID51140发SIGINT：未完成全量，收据8146P/22S、exit_status=2；包装器rc4，明确拒绝退出码矛盾。中断后tmp_path清理有KeyError；未以此判产品bug或重跑求绿。包装器临时完整stdout已被自己的退出清理删除，本目录只能保留实际留下的尾部与收据，不声称完整中断日志仍在。

## 未验

小片基于main f783f19c8，三领域直接基于#831。新main f2c3e9e1a24f（#830）及三领域联合组合未验；历史原四题、财务R6/R3自然失败未翻案；runtime不签跨进程driver/lease/未知效果对账/exactly-once。领域新独立报告另归档，不把此包当它们的批准。
