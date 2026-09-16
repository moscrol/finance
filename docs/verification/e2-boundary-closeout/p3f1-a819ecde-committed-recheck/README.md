# P3f1 固定提交作者复验

被测提交：`a819ecde6529784da06401e59152a476343f9011`。
干净检出：`/tmp/e2-p3f1-frozen-a819ecde`。这是作者复跑，**不是独立 QC**。

- 八文件回归：**249 passed in 2.24s**，禁止尝试 **0**，pytest/shell exit0。
- 归档检查器合成 Git 测试：**15 passed in 1.94s**，exit0；该组不使用 IO 审计启动器。
- 本片六个应用/测试文件 Ruff：通过，exit0。
- 固定提交归档校验：P3f1 **68/68**、P3e 独立归档 **26/26**、被否 P3f 归档 **27/27**；全部哈希匹配。
- 测前和测后 Git status 为空；六个文件与候选快照哈希逐一相符。

回归测试集合与启动器见上级目录 `p3f1-source-binding-20260915/launch.json` 及
`launcher.py.txt`。本轮用唯一 NAME `committed-regression-v1`；临时隔离数据不入库。
Python audit + native DuckDB connect 拦截不是操作系统沙箱；不认证其他 native IO。

原件逐字节复制，SHA-256 清单只排除自身。本目录保存的是被测提交的复验记录，
因此加入记录的文档提交必然晚于被测提交；不能将后来的 HEAD 伪写为本轮被测版本。

结论仅限当前明确 material_only 的来源身份绑定及已列控制；不覆盖 controller 提示词
历史过滤、pending/已有frame恢复重验、跨轮权限、Episode历史正文交付或最终答案。
相邻测试早先110P但100次禁止尝试、shell exit3的失败仍在原作者归档；本轮没有洗掉它。
无独立QC、无全仓/前端/E2E合入结论；未推送、合并或部署，正式T2→T3/Knevo未运行。
