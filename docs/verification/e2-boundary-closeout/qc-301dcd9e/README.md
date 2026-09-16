# E2 P3b / P3c + 返修：独立审查归档

审查目标 `301dcd9e1eef5095424027ffa703bfeab2472cc6`；原件日期 2026-09-14。
完整裁定见 [report.md](report.md)，原始范围见 [prompt.txt](prompt.txt) 与 [finish-prompt.txt](finish-prompt.txt)。报告逐字节保留，不把原报告里的 `/tmp` 改成归档路径。

## 裁定与分母

- P3b 通过、P3c + 返修通过，均仅限本片；同型号独立上下文，不称不同模型交叉验证。
- 原独立探针 **36 passed / 1 failed**；跟踪原针仍 **1 failed / exit 1**。红针在 deadline 后二次进入 runner 适配器，未生成晚结果，不是产品归属错误。
- 修正版 **37 passed**（36 项行为 + 1 项汇总）；晚结果两种账本条件各 5 次，共 **10 passed**；重点 **38 passed**；相关回归 **106 passed**。全部禁止 IO 尝试为零。各组不相加为独立覆盖数。
- 原 7 个 assert 均保留、修正后 18 个；保持原 `.08s` deadline，未增加 sleep / 调整应用 / 修改原题或原 46 针。
- 不等于全仓、完整 P3、P4–P7、产品验收、合并或部署许可。作者全测数不是本报告的放行依据。

## 存储规则与复现

归档所有 46 个 manifest 条目及 manifest 本身，并追加两份 prompt 与最终报告。为避免 pytest 自动收集故意失败的历史探针，以及日志忽略规则，原 `.py` / `.log` 文件名追加 `.txt`；**字节不变**，其他文件同名。`sha256-manifest.json` 仍使用原文件名。

校验（在本仓根目录；无 IO 副作用）：

```bash
python3 - <<'PY'
import hashlib, json
from pathlib import Path
root = Path('docs/verification/e2-boundary-closeout/qc-301dcd9e')
manifest = json.loads((root / 'sha256-manifest.json').read_text())
for name, expected in manifest.items():
    archived = name + '.txt' if Path(name).suffix in {'.py', '.log'} else name
    assert hashlib.sha256((root / archived).read_bytes()).hexdigest() == expected, name
print(f'{len(manifest)} archived source hashes verified')
PY
```

实际测试命令见报告 §五；launcher 使用固定 `/tmp/e2-qc-301dcd9e` 代码树、`-data` 临时数据、`-evidence` 证据目录。若原临时目录丢失，先在该位置检出固定 revision，按上述映射还原证据原文件名，再复现；**不要对现有证据目录原地覆写重跑日志**，另设 `QC_LOG_NAME` 与 basetemp。跟踪原针预期失败，不得把它混入产品回归或改成 xfail 隐去。

2026-09-14 接续宿主实际完成：46 个源文件及其归档副本哈希逐项一致；三个 diff 与报告指定 git 区间逐字节一致；六组日志 summary、5 个 pytest exit 文件及各 IO 计数复核；目标工作树仍 clean @301dcd9e。这是归档完整性复核，**未重跑测试、不是第二份独立审查**。

`git diff --check` 对归档原件会报告原始 diff 的空白上下文行及 pytest 日志尾空格；这些不是应用/新增说明的空白缺陷。保留字节供哈希验证，不为消除展示警告修剪历史证据；新增说明与产品门/inflight单独做 diff 检查。

大型 harness 会话 JSONL 和临时 DuckDB 不入 Git：原 `/tmp/e2-qc-301dcd9e{,-finish}.jsonl` 与专属 `-data/` 均保留，未清理。审查过程服务退出码不作为 pytest 结论。
