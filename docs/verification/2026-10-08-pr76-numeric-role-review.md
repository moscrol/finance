# #76 数字角色修复：源码 PR 复核入口

日期：2026-10-08。状态：送审候选，不部署；完整CI以本PR的实际Checks为准。

## 交付方式修正

上一轮补丁只在**云端沙箱**，不是Mac；未推送，其他Agent无法复核。SHA256只标识内容，不能证明正确或替代CI。上一轮444项为隔离快照相关测试，不是全仓门禁。

本轮修复进入真实源码与 `intelligence/tests/test_temporal_numeric_roles.py`，由既有CI收集，不再把docs里的补丁当产品修复。

会话固定分支为 `arena/a3bfea49-finance`，不能新开分支。处理方式：

1. 本地48项未提交路径保存在stash `334c6ab8e6d8f0ac6c7494fff430457c3b5a7b64`，未drop；独立crocodile-flight目录不动。
2. 快进到此前已推送的d340e3a6；该日历/复盘成果由#77明确接续。
3. 以显式revert提交1326225b撤销本分支的该批差异，再合入origin/main（本地整合，不是合并GitHub PR）。旧提交未被删除，也不强推；#77和main不受此撤销影响。
4. 将本次修复应用到main@e3f88f2974f8cce2a74af9fbb1c6d9037ade746a。相对main的净差异只包含本次三个服务文件、新回归与送审文档，不重复夹入日历/复盘工作。

## 本轮具体改动

- `temporal_contract.py`：共享数值角色过滤，局部日期用途与数量角色分离；不把5/10/20截成5/10；识别日均线等周期单位；保留合法日期与追问语法。连接日期采用迭代而非递归，避免长列表栈溢出。
- `episode_tools.py`：D4快照生成器不再无条件标`current`，使用`unknown`并说明“匹配查询快照不等于运行日最新”。这不等于将合法历史证据判为无效。
- `research_tool_registry.py`：mainline_context的独立防线，以运行上下文today而非解析出的target/cutoff核对current标签。与运行日不同的已知旧日期降为historical，缺运行日/缺源日期/未来日期降为unknown。原有未来证据权限过滤继续生效。此处不自动把unknown升级成current。
- 新回归39项在正式测试目录，包括问题中列出的所有可见问句、真实取数/投影、主动注入错误freshness的独立测试，以及1200项日期列表。

## 多日期：明确收窄承诺

本轮**没有实现离散多日期研究合同**。`今天和9/30比`、`9/29和9/30对比`及涨停变体，解析出两个日期后进入clarify，向用户说明分别查询或明确是否研究连续区间；禁止静默只取一天、忽略今天、落回最新日或擅自把两点变连续窗口。测试确认在resolver/取数之前停止，capabilities为空。

连续窗口（9/28至9/30）、显式资料截止和已有追问继承继续支持。独立短数字回复、未覆盖的自然语言表达仍可能有歧义；这不是通用语义理解完成的声明。

## 已验证与待验

- 本轮最初重放上一候选，确实发现`止损设在1/3处`仍误判，`9/30收盘`与`9/30的连板梯队`被误伤。已补入源码测试并修复，不沿用“444全绿所以正确”的结论。
- 整合到当前Git工作树后，9个相关测试文件 **518 passed in 61.28s**；随后只增加长日期列表用例，新文件 **39 passed in 3.60s**。前述518项不是增加该用例后全套重跑的519项，不移签计数。
- `.venv-workbench/bin/python -m ruff check .`：通过。
- 本机Python3.11与dev lock，不等于正式Python3.12完整门禁；完整CI需以本PR提交的实际运行结果为准。
- 真取数测试使用合成DuckDB的01-03旧日哨兵与10-07新数据，经过控制器、上下文、实际注册工具及模型输入投影；socket禁用、模型解析关闭，未跑付费答卷。
- 独立freshness测试故意让provider返回01-03且current，即使上下文目标也是01-03，注册边界仍改为historical；历史事实保留，不能伪装为运行日当前行情。
- 未取得审查方`scratch/pr76_acceptance_probe.py`文件；依据消息内明确列出的14条问句补测，不声称跑过该未共享的20句脚本。

### 可复跑命令

```bash
.venv-workbench/bin/python -m ruff check .
.venv-workbench/bin/python -m pytest intelligence/tests/test_temporal_numeric_roles.py -q
.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_temporal_numeric_roles.py \
  intelligence/tests/test_query_understanding.py \
  intelligence/tests/test_temporal_contract.py \
  intelligence/tests/test_market_context_contract.py \
  intelligence/tests/test_task_frame.py \
  intelligence/tests/test_mainline_history_scope.py \
  tests/test_history_permission_inheritance.py \
  tests/test_history_expression_contract_boundary.py \
  intelligence/tests/test_episode_tools.py -q
```

## 未完成与禁止推断

- 完整CI尚须核查，不把已出现的部分绿勾当完整通过。
- 独立多日期研究尚未实现，本轮只能安全澄清。
- 新鲜度防线范围是D4/mainline_context，不是全供应商统一新鲜度系统，也不证明数据源完整或最近一笔已到货。
- Mac夜跑、8792 readiness、实际生产效果仍未复核；不重复同步或写生产库。
- 不合并、不关闭其他PR、不删枝、不部署。由当前owner和独立审查确认后再安排发布。
