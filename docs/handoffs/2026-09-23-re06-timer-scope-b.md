# 2026-09-23 RE06 计时授权选择 B

## 授权与身份

用户对 #73 的 A/B/C 决策回复原话：`b`。据此实施独立计时 scope；不授权部署、生产台账迁移、合 main、清理工作树或真实模型验收。

原树 `~/fwp-wt-e2-re06-resume-0922` 和共享脏主树未修改。本轮使用预留的隔离树 `~/fwp-wt-wave2-re06-0923`，新枝 `fix/re06-timer-scope-0923`：

- 固定 main：`ffd1b7f1572067e9a4c7e3a5845e99cf7f876cfb`。
- 原任务源：`100dcb32abd78b7f529d83332731a70704faeeb3`。
- `merge-tree --write-tree` exit 0，预演树 `a2739a155bfd5254e3dac806f0d7e9aa63eca0a3`；不当作行为通过。
- 候选整合：`486ae9188`，保留原 E2、共用折叠和锁内复核。
- 本轮代码：`4bb3bf0cb19f0992ccb2a02bae75b6f16145d1dc`。只在本地提交，未 push/开 PR/合 main/部署。

## 发现与选择

1. 旧按钮以 `workbench-activity-v1` 授予和撤回 `research`+`logging`，所以停计时会关自用测量。
2. 只改前端 scope 仍不够：写门把任何同意记录视为表达过测量意愿，首次只有计时授权会让测量所需范围不足。必须在读写两侧使用同一个测量域分类规则。
3. 新控件改用 `workbench-activity-v2` / `activity-timer`。停止、切会话、pagehide、失败补撤回都使用独立范围。条款和状态文字同步说明同意互不改变。
4. `product_value.consent.measurement_scopes` 为读写共用分类器。纯计时返回 None，不进入测量意愿时间线；其他部分授权、空集、真正撤回保持原语义。折叠排序、未来生效、同毫秒撤回优先、身份过滤和锁内复核不改。
5. 旧版兼容只认：version=v1、scope 恰为 research+logging、source=frontend、protocol=workbench-self-use/v1、pilot 为 workbench: 前缀、participant=owner 且无 task。授权与撤回对称解释为纯计时；不同来源/身份/协议/范围/任务不转换。

| 方案 | 取舍 | 决定 |
| --- | --- | --- |
| A 只改文案 | 耦合仍在，每次停计时都关测量 | 未选 |
| B 新 scope + 读取兼容 | 目的隔离，同时保留历史字节与哈希 | 用户已选并实现 |
| B 改写历史台账 | 要迁移、改哈希和生产授权，非本轮范围 | 不做 |
| C 仅写门忽略版本 | 读写口径分叉，且可能忽略真正的撤回 | 不做 |
| 只改前端字符串 | 首次计时仍会翻掉自用默认 | 不采用 |

兼容不是补写授权：只有计时记录时，写侧保持既有自用默认，读侧仍为未知；旧计时 grant 不能充作试点授权。真实测量撤回不会被重新开计时覆盖。原始事件和内容哈希不改；重新计算含旧计时记录的测量结果可能变化，旧收据不能充当新口径收据。本轮没有重算生产读数。

## 验证

解释器一律主树 `.venv-workbench/bin/python`。所有测试均为串行定向回归，无真实模型请求，API 测试使用隔离临时 users 根。

干净代码提交 `4bb3bf0cb`：

- `test_re06_activity_consent_gate_effect.py` + `test_re06_consent_fold_shared.py` + `test_re06_consent_gate_toctou.py` + `test_research_evolution_i11_consent.py`：89 passed。
- 正式收据：`~/.finance-runtime/test-receipts/20260923T042307Z-4bb3bf0c-1e7b698d6fd6.json`，revision 完整匹配，dirty=false，collected=89，failed/error=0；这是四文件局部收据，不是全仓。
- 前端 `ResearchActivityControl.test.tsx` + `researchActivity.test.ts`：9 passed，单 worker。

提交前同一实现的额外回归（不移签为干净提交全量）：

- `test_product_value_*.py` + `test_e2_local*.py`：164 passed。
- 六份 `test_research_evolution_{api,falsification,io,rework,store,visibility_timing}.py` + 三份 `test_re06_*.py`：195 passed，包含前述 79 项核心测试。
- 合计去重 369 个 Python 用例通过；这个数字不是全仓分母。
- 前端 typecheck、修改文件 ESLint、Python 修改文件 Ruff、diff --check、提交钩子均通过。

三项进程内变异（不改磁盘源码，不覆盖正常测试收据）：

| 拆除点 | 故意替换 | 结果 |
| --- | --- | --- |
| 共用隔离 | 两侧 measurement_scopes 直接返回原 scopes | 新旧版本默认/未知用例 6 failed |
| 旧版兼容 | 分类前把 consent_version 改为 no-legacy-alias | 新旧共存用例 1 failed |
| 锁内复核 | `_measurement_consented` 收到 store 参数时直接 True | 并发撤回用例 1 failed，实际多写 run_started |

每项为 pytest exit 1 的断言失败，不是收集错误；恢复进程后 195 项回归和干净提交 89 项均绿。未宣称完整 mutation suite 或独立 QC。使用既有 pytest 进程内替换作为一次性反证，未新增通用测试运行器；长期保护落在正式回归用例中。

JUnit 原件：`~/.finance-runtime/reviews/re06-timer-scope-20260923/`，含 committed-consent.xml、committed-frontend.xml、两个扩展回归 XML 和三个 mutant XML。原始 `/tmp/re06-timer-scope-0923/` 未删除。

## 边界与下一步

- 12:21 资源快照：load 17.74/28.65/24.36，pytest 5 个，可用 71.31 GiB。未满足全量 load<=8、pytest<=2；未跑全仓 Python、完整 frontend/build、E2E 或完整 registry 叶子，不可合并。
- #75 独立 K3 QC 未启动，本轮不是第二方结论；#76/P7 真实隔离验收未做。
- #73 原工单要求的 17 处事务同族清单未在本轮重新逐项审计，不照抄成新候选证明。
- 代码地图查询 status=empty/vault=unavailable，未据此做架构断言；定位使用实际源码。
- 先补固定候选四叶和 #75，再申请合 main。若需推送/开 PR，明确这是新候选，原枝和旧收据保留。不部署，不改生产 8792，不回写生产 users，不删除工作树。
