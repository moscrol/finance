# RE06 事务同族核对：固定候选 f9ce5c6b2

## 身份与口径

- 候选：`f9ce5c6b296492b423400ad66d333784a4be13bc`，树 `/Users/a77/fwp-wt-wave2-re06-0923`，分支 `fix/re06-timer-scope-0923`；核对首尾 clean、revision 不变。
- 固定基线：`ffd1b7f1572067e9a4c7e3a5845e99cf7f876cfb`；原任务源 `100dcb32abd78b7f529d83332731a70704faeeb3`。
- 作者侧静态核对，不是 #75 独立 QC，也不是新一轮行为测试。
- TOCTOU（检查与使用之间的竞态）在本单的范围：依据可变台账作出许可判断，锁外判断之后有并发撤回，锁内追加之前却未重新判断。
- 分母是 `intelligence/services/research_evolution/*.py` 和 `intelligence/api/research_evolution.py` 中对 `transaction` / `try_transaction` 的直接方法调用，不是整个仓库所有事务。
- Python AST（语法树，按代码结构枚举而非数文本行）得出 **17 个业务调用点 + 1 个底层 `_locked` 包装调用**。注释、函数定义及测试里的调用不计。原工单“全仓17处”的措辞在此收窄，不把它升级成全仓无竞态证明。
- 枚举及源码 SHA256 原件：[transaction-inventory.json](2026-09-23-re06-timer-scope/transaction-inventory.json)。以下行号只对应上述固定候选，文件均在 `intelligence/services/research_evolution/`。

## 逐项判定

| 序号 | 文件:行 / 函数 | 分类 | 决策与副作用核对 |
| --- | --- | --- | --- |
| 1 | `facade.py:727` `create_binding` | 锁外只是快路径 | 锁外 `find_binding` 可直接重放；新写仍走锁内 `append_binding` 的既有 id/内容对账。并发变更不会因锁外“未找到”而跳过写入器的冲突检查；不宣称任意并发载荷都能成功重放。 |
| 2 | `facade.py:792` `_maintenance_action` | 正例 | 锁内读动作、当前项和修订号，再校验版本并追加；注册升级也传入 `txn`，不另开非重入锁。 |
| 3 | `facade.py:1220` `fold_run_terminal` | 正例 | 锁外仅定位链接；锁内复核幂等键、当前项状态和请求代际，再生成终态折回事件。旧代际不能直接迁移新代际状态。 |
| 4 | `facade.py:1335` `bind_pending_rejudge_run` | 正例 | 锁内核验启动坐标，读取已有 run 归属后才追加；冲突归属返回而非追加第二份。 |
| 5 | `facade.py:1534` `pending_task_continuation` | 无决策性写入 | 锁内只读本会话任务记录并返回 continuation，本事务没有台账追加。此判定不证明返回后整个消息接受过程原子。 |
| 6 | `facade.py:1634` `_select_task` | 正例 | 幂等检查、视图取数、任务存在性判断、选择事件及动作记录均在同一事务内；直接用 `txn`，不调用会再次加锁的 `_store_event`。 |
| 7 | `facade.py:1799` `_reveal_exercise` | 无同意许可判断 | 写的是已发生曝光的流程收据，曝光由独立的验证域入口先登记；不依据测量授权决定 run 生命周期事件。跨存储一致性不在本次证明范围。 |
| 8 | `facade.py:2070` `_store_event` | 无同意许可判断 | 通用的已校验事件追加，锁内写入器检查幂等；含 `consent_changed` 的入口不能要求已获测量同意，否则首次授权和撤回本身无法入账。`ingest_events` 的白名单/owner 盖章在调用前。 |
| 9 | `facade.py:2084` `register_artifact` | 无可变许可判断 | 检查配置种类后锁内发布不可变配置；同 id 异内容由存储层拒绝。 |
| 10 | `facade.py:2105` `record_process_receipt` | 无同意许可判断 | 检查收据种类与 id、固定 owner 后追加流程收据，不是自动 run 测量事件。 |
| 11 | `facade.py:2117` `store_protocol` | 无可变许可判断 | 锁外纯计算冻结协议及内容哈希，锁内不可变发布。 |
| 12 | `pilot_io.py:94` `cmd_register` / protocol | 无可变许可判断 | 校验并冻结输入协议；显式 `--apply` 才在锁内发布。 |
| 13 | `pilot_io.py:114` `cmd_register` / assignment | 无可变许可判断 | 显式导入的分配记录，迟登标记保留；锁内不可变发布，不生产自动生命周期测量事件。 |
| 14 | `pilot_io.py:124` `cmd_register` / policy、pack | 无可变许可判断 | 显式注册领域配置；锁内内容去重或拒冲突。 |
| 15 | `pilot_io.py:167` `cmd_import_events` | 正例 | 输入先整批校验；锁内重新对照既有台账的 id/摘要，确认整批无冲突才逐条写，避免写半批才发现冲突。手工渠道不能导入 server 专属事实。 |
| 16 | `pilot_io.py:231` `cmd_rebuild` | 不属于本次同意写门 | 锁外读取事件并计算收据/总结，锁内发布不可变结果；读侧按事件自身时间过滤同意。没有声称结果包含发布时刻最新追加的事件，也未证明协议/多台账的全局原子快照。生产重算须另授权。 |
| 17 | `run_observer.py:218` `_record` | 真成员，修复保留 | 锁外同意快筛之后，`try_transaction` 内对同一 `now` 和 `txn` 重新调用 `_measurement_consented`；只有通过才追加。`run_started`、`run_finished`、`cost_recorded` 共用该入口。计时分类修改没有绕开复核。 |

底层另记 `store.py:203` / `_locked`：已有事务就复用，未在事务内才调用 `transaction()`，没有业务授权谓词。`transaction` / `try_transaction` 的定义不算调用点；API 文件无直接调用点。枚举不能覆盖反射、别名调用或其他领域的锁。

## 保护测试与证明边界

固定候选已有以下测试入口，**本轮只核对源码存在和断言内容，没有重新执行**：

- `test_re06_consent_gate_toctou.py`：撤回落在构造与追加之间、不变的正向对照、未来生效撤回、按事件时间判定、关闭时不争锁、最后一次复核确在锁内。
- `test_research_evolution_rework.py`：S1 同修订号并发只接受一个；S2 整批导入冲突零写；T2 旧代际迟到不能折回新代际；Q6 任务选择重放/冲突；Q9 测量锁不阻断 run；T5 锁文件打开失败释放进程锁。
- `test_re06_activity_consent_gate_effect.py` 与 `test_research_evolution_i11_consent.py`：v1/v2 计时不撤回测量，不把真正撤回重新授权，三类生命周期事件共用门。

历史 `4bb3bf0cb` 的 89 项及变异回执仍只属于原 revision，不移签 `f9ce5c6b2`。本轮没有新 pytest 进程，没有新行为通过数。

## 复算方法

在固定候选根执行下列标准库枚举；不导入产品模块、不读生产台账。输出的 18 行中，`store.py / _locked` 单列，其余 17 行与本表核对。计数正确不等于语义正确，每一行仍需人工沿调用链阅读。

```python
import ast
import subprocess
from pathlib import Path

paths = subprocess.check_output([
    "git", "ls-files", "--", "intelligence/services/research_evolution/*.py",
    "intelligence/api/research_evolution.py",
], text=True).splitlines()
for path in paths:
    tree = ast.parse(Path(path).read_bytes(), filename=path)
    parents = {child: parent for parent in ast.walk(tree)
               for child in ast.iter_child_nodes(parent)}
    for node in sorted(ast.walk(tree), key=lambda n: getattr(n, "lineno", 0)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"transaction", "try_transaction"}):
            continue
        parent = node
        while parent in parents and not isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
            parent = parents[parent]
        print(path, node.lineno, getattr(parent, "name", "<module>"), ast.unparse(node))
```

没有新增通用审计工具：本次语义分类依赖领域合同，一次 AST 枚举和可复跑片段足够；不把文本匹配包装成自动证明。
