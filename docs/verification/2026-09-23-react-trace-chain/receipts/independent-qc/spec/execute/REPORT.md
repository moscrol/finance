# Execute 阶段终稿（spec 轴，#81 / PR #832）

## 简报（≤500字）

正控按要求单独首跑：真实 exit 1、AssertionError("intentional probe_bug control")，归 probe_bug，不计产品失败。explore/commands 原始输出抽核（002/006/007/014/015/018/023/024/029）与 REPORT 一致。

自造探针实跑：`probe_c5_history_pages.py` 5/5 通过（exit 0）——在真实 `_result` 上验证绝对 sample 行号跨页稳定、next_offset 三种 null 边界、分页提示语、kwarg offset 覆盖陈旧 payload offset 且不改写调用方 dict、truncated 透传，C5 函数级契约成立。`probe_c5_registry_pages.py` 3/3 失败（exit 1），但全部在 `_registry` 夹具内 `sqlite3.connect` 报 `unable to open database file`；独立复现证明 work/tmp 下普通文件创建成功、内存 sqlite 成功、文件型 sqlite（含非 WAL）一律 CANTOPEN——属沙箱拒绝文件型 sqlite 的环境阻断，非产品契约违例，也不是有把握的 probe_bug，原失败保留待裁决。

未跑：probe_c6_dangling_repair.py、probe_c6_verifier_wiring.py（仅 py_compile）、全部7个作者回归文件；C6 与 C5 registry 级无行为证据，不裁 PASS。沙箱另发现：mkdir -p、bash heredoc 被拒；pytest 需 `-c 候选pytest.ini --confcutdir` 才能避开对 review 根目录 stat 的 EPERM。工具在写完 sqlrepro3.py 后关闭，该复现与 EXECUTE.md 落盘未完成，本消息即为终稿账。

## JSON

```json
{"stage":"execute","axis":"spec","revision":"d1b30e1a068ccd0559f091f3c664ca2ca82f1e7c","baseline":"626d8a508c1c988ff094110b371987e6afdcdd15","complete":true,"author_tests":{"passed":0,"failed":0},"reviewer_probes":{"passed":5,"failed":3},"positive_control":{"classification":"probe_bug","observed_exit":1},"product_findings":[],"limits":["probe_c6_dangling_repair.py 与 probe_c6_verifier_wiring.py 仅 py_compile 未运行，C6 零行为证据","7个作者回归文件全部未运行","probe_c5_registry_pages.py 3失败为沙箱阻断文件型sqlite(CANTOPEN)之环境问题：同目录touch/普通open成功、:memory:成功；非产品失败亦非确证probe_bug，原失败保留","sqlrepro3.py(O_RDWR/预建文件/URI复现)已写盘但工具关闭未运行","work/EXECUTE.md 因工具关闭未能落盘，账目以本终稿为准","沙箱怪癖：mkdir -p与heredoc被拒须直mkdir/write落盘；pytest须--rootdir+ -c候选pytest.ini+--confcutdir避开review根stat EPERM","C1-C4无产品增量diff未探；C6与_restore_lost_observations交互、N条豁免规则沿explore未解","不裁PASS：C5函数级通过仅为部分 seam 证据"]}"
```
