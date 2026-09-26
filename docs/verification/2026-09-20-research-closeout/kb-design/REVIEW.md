# KB PR155 设计复核与最终代码独立补验

结论：单写者、冻结代、单 current 和整代发布的设计合理，可继续现有路线；本轮补齐最终修复版的独立动态缺口。未发现需要重写 KB 维护架构的新阻断项。生产消费侧还有一项实证状态缺口，须进入后续金融接缝片；不得把本报告当作生产切换或真实上传验收。

## 身份与证据层次

- KB：`/Users/a77/kb-wt-guarded-maintenance-0920@3a21010323eababb54ce8519093fd60dbacb9451`。相对代码提交 `7e07addb466385085e21ccaf3d06bf23c6e4b0a1` 仅 4 文档，源码无差异；相对基线 `1254224be89e2c4974350b7f3e985dbedb5dc043` 共 25 文件。
- 金融：`/Users/a77/.finance-runtime/open-work-execution-20260920/gate-generation-final/finance-workspace-private@4ace5ec2e9b7735d90eb15bc2351fa193c1120b8`。
- 两树运行前后均干净、HEAD 不变。未修改原树、生产索引、防写 flags、安装 hook、launchd、8792；未上传、未调用真实模型。
- 原作者 `911 passed` / 定向 `80 passed` 是历史作者收据，本轮未重跑全量，不计为独立裁决。
- **原独立探针 11 个行为场景：全部通过。** [`verified-results.json`](verified-results.json) 记录前后身份、命令、退出码和原探针哈希。9 个 Spec 场景沿用原输入/判据；2 个 Quality 激活反例保留原故障注入主体，只重绑定 TREE/OUT/SHA。旧脚本“漏洞应复现”断言被外层捕获，单独验证修复判据；详见 [`activation/replay-results.json`](activation/replay-results.json)。
- **另写独立真实金融 worker 探针：通过。** 不调用作者测试函数；自行建立 hash/BM25 两页源、v1/v2 内容真实不同的两代。普通/全文分别热查询两次、L1 负例、旧进程拒答、新代重启、显式回滚再启均通过，6 个自建子进程全部关闭。8 行阶段记录见 [`worker/results.json`](worker/results.json)，源码 [`probe_finance_worker.py`](probe_finance_worker.py)。
- **另外重跑作者新增的 12 个正式控制写回归：12 passed / 61 deselected，12.90s。** 仅补充回归证据，不加进上面的独立 11 场景。日志 [`final-control-regressions.log`](final-control-regressions.log)。

## 设计判断

1. `flock` 绑定持久锁 inode，退出后由内核释放；请求队列用另一个短锁，使耗时构建不吞后续刷新请求。比 PID 是否存在或删除旧锁可靠。最终补丁在慢验证/子进程/远端读取后重核根与锁身份，原反例已关闭。
2. 新代绑定实际代码字节、解释器/依赖版本、源集合及两索引。源枚举先于切块，非空零块不能从验收分母消失；冻结源独立于可编辑资料目录。冻结代适合回溯和显式回滚。
3. 单 current 原子替换，启动一次解析 manifest，并清除金融侧优先的 VECTOR_INDEX_DIR。避免普通/全文独立指针产生混代；真实 worker 在换代后拒用旧缓存，重启后确实读到 v2 内容。
4. approve 绑定精确 manifest 字节，属于操作者审批记录，不等于代码自行得到业务授权。publisher 显式仓库/标签、只发完整批准包、下载回读哈希和最终 tag 复核合理；上传中 tag 漂移的原反例已确认失败且保留证据。

## 已确认的金融状态接缝：退役 worker 仍报告 ready

反例在固定金融 `4ace5ec2`、隔离真实进程中复现：两类旧 worker 首先热查询成功；activate v2 后均返回 `returncode=1`，stderr 含 `worker generation retired`；此时各自 `status()` 仍是 `state=ready, active=true`。8 行阶段记录中的两条 `retired-after-switch` 保存原始响应与状态。

调用链与原因（行号均针对上述固定金融提交）：

- `intelligence/services/rag_worker.py:150`：`query → _serve → _query_locked`。`_serve` 第 165–168 行仅在成功时刷新 ready，对非零返回没有退役状态处理；此次拒绝是正常 WorkerResponse，不会走异常处理。
- 同文件第 202–208 行：实例 `status()` 直接回报历史 `_state`，`active` 仅由进程存活决定，没有 current 身份校验。
- 同文件第 597–615 行：聚合 `status()` 只要所有实例仍 ready/active 就算 ready。
- `intelligence/api/app.py:2735` 的 `/api/readiness` 经第 2744 行调用聚合状态；第 2776–2781 行据此令 `rag_worker` 分项为真。**本轮没有启动 HTTP 服务，不能据此声称整个 readiness 实际返回通过**；其他 readiness 分项另有判据。

这不推翻 KB 已实现的拒答门，但说明“状态绿”还不能证明已切代。现有方案明确停旧服务→activate→重启/预热，严格执行可规避；不能扩写为允许热切指针后依赖 readiness 自动发现。

建议最小修复留在金融消费边界，不扩 KB 架构：

- worker 创建/启动时固定预期代际身份与 current 根；不能让后续 ambient 环境变化给旧实例换身份。
- 对受管 worker，`status()` 在返回 ready 前读取同一个小 current，比较绑定代名/manifest SHA；不匹配视为 retired，缺失/损坏/换链视为 unavailable，聚合与 readiness 均不能通过。无需每次扫描整份大索引。
- `_serve` 收到明确的 generation-retired 结果时同步保留退役原因；不要把任意查询参数错误一概当退役，也不要自动用旧路径重启并恢复绿。
- 保留真正非受管路径：无代际绑定且索引实际目录/祖先无 `.rag-generation.json` 时沿用原行为；受管目录（含软链解析后）缺绑定应拒绝，不能降为 legacy。
- 回归落 `intelligence/tests/test_rag_worker.py` 与 `intelligence/tests/test_rag_readiness.py`：先暖两类 worker，切 v2 后**不先发查询**就读状态应非 ready；再发查询拒绝；关闭旧实例/按新绑定创建并预热后才恢复 ready；加入真实 legacy 无 current 的兼容例及受管缺绑定例。

最小验证命令（在后续金融修复的干净检出执行）：

```sh
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests/test_rag_worker.py intelligence/tests/test_rag_readiness.py -q
```

## 尚未覆盖及下一步

1. 将本次独立证据归入最终验收记录；原“只有静态增量通过”的描述可由后续文档收尾准确升级，不挪用 1bd 的身份。
2. 先完成上述金融状态接缝及离线回归。完整 Workbench Episode/其他结果缓存仍未做真实入口验收；当前 `kb_rag._cache_put` 对带 receipt 的结果明确不缓存（固定金融 `kb_rag.py:596`），故没有证据支持“本轮已发现结果缓存泄漏”的额外断言。
3. 真实 Gitea 权限、上传、仓库资产回读只验过替身；生产规模 BGE/混合检索的启动时间、内存与回答质量未由 hash/BM25 小样证明。后续实际切换按已批准运行方案验证普通/全文实查、旧 PID 清零、readiness 分项和回滚收据。
4. 本轮仅只读复核与隔离验收；没有实施金融修补，也没有为解除防写、恢复 hook、启动服务或发布资产新增授权。

使用 leila-runtime 环境流程；工具为本地 Git、指定 Python、原独立探针及自写离线进程探针。下一动作由根代理串行安排金融状态接缝。
