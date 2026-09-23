# #76 L6 离线预检与待授权协议

## 状态

`BLOCKED_AUTHORIZATION_AND_ORDER_DECISION`。本轮只读取历史原件，没有新模型请求、数据冻结、旁车启动、合入或部署。`protocol.draft.json` 的 `can_execute=false`，不是已经获批的执行协议。

候选 PR #868：`31f1b40dd788d36c71da249d59fb769c50d7cd30`；完整工程收据仍绑定 `7ad61a0d3`。本次只是 docs 后续，不移绑原工程收据。

## 发现的前置问题

1. **工单顺序成环**：#72 要求严格探针后先真实改稿、再 #75 终审；#75 要求代码 PR 合入前独立审查；#76 L6 又指定 #72 合入后的 main。建议授权修订为「冻结未合入候选跑 L6 -> 独立终审 -> 另行确认合入」。当前尚未同意该修订，不能自行换成候选实测或先合 main。
2. **旧启动入口不满足新端口红线**：`scripts/compare_adaptive_research.py:48` 固定首选 8796，`intelligence/eval/live_probe.py` 回退扫描 8796--8820，均落在 #76 禁用的 8780--8830。该 compare 命令也不负责数据冻结、授权检查和完整 closure，不能直接当 #76 runner 使用。可复用其真实 Episode 协议，提交侧可用已有 `scripts/workbench_probe.py` 的显式 `--port` / `--skill-mode hybrid`，但仍须配套冻结与收尾控制，不等于现在可以直接开跑。
3. **历史样本不能冒充候选验收**：三题源协议均请求 glm-5.3-flash，而待验方案为 K3 写手 + flash 判官；Q3 源协议 `dirty=true`，所有旧样本 `data_frozen=false`。题面可原样复用，旧记录可作判定器失败夹具，不能算新代码效果或严格 A/B。
4. **判官状态不是内容验收结果**：Q3 历史字段为 `judge_status=repaired`，同时有六条 `novel_numeric_condition` 删除记录；这六条须逐句检查证据、单位和公开稿去向，不能只按 repaired 签通过，也不能只凭 bound_evidence_hashes 就认定六条全部有充分证据。

## 本轮离线执行

复用候选中的 `scripts/inspect_adaptive_research.py`，对 Q1 / Q2 / Q3 / absence 原件分别使用树外 `--output`，没有启用 `--project-current-judge-status`，所以保留的是历史捕获字段，不是当前代码重建的判官请求。

输出根：`~/.finance-runtime/reviews/pr868-l6-preflight-20260923-1220/`。每个目录含 `off.json`、`controls.json` 和 `sha256.json`。

| 原件 | 历史 revision | dirty | 捕获的 judge_status | 删除记录 | 新清单校验项数 |
|---|---|---|---|---:|---:|
| Q1 寒武纪 | d9a6f6a81 | false | repaired | 0 | 17 |
| Q2 东阳光 | f80bad256 | false | repaired | 0 | 15 |
| Q3 固态电池 | f80bad256 | true | repaired | 6 | 14 |
| 09-22 absence 东阳光 | a1da0c98e | false | unavailable | 1 | 15 |

清单项包括原件与本次提取件；61/61 当前哈希复核通过，不宣称有 61 份独立样本或历史封存链全审计。表内删除数不是误删定性。旧 `elapsed_seconds` 属历史运行耗时，本轮没有重新请求模型。

相关既有测试 `tests/test_compare_adaptive_research.py`：**9 passed**，候选树执行前后干净，收据 `~/.finance-runtime/test-receipts/20260923T042251Z-31f1b40d-8b9018e2adae.json`；JUnit 在证据根 `inspector-tests.xml`。这是提取器/探针的离线工程回归，不是 L6 三题验收。

## 待批准的范围

- 候选固定为 `31f1b40dd788d36c71da249d59fb769c50d7cd30`，独占 detached 检出；代码若变化重新议定，不追着动态分支运行。
- 三道原题逐字固定，SHA256 在 draft；各首发 1 次、重发 0、续问 0，串行运行。网关探针最多 1 次，HTTP 400/429 停批，不换模型/账号硬顶。
- T900 / Episode 600 / 单发 75 / 修订 30 / 每次核验共享窗 150 秒不变。150 秒不是整个用户回合判官的总预算。
- K3 写手、glm-5.3-flash 判官；记实际 served model。Q2 保持 local_only 四只读能力，不开 derived_calculation。
- 授权后才复制只读市场库与匹配快照、写 manifest；KB/外部来源若未冻结要明确披露，不称全输入冻结。
- 拟用 19897 / 19898（未启动、未预留），起跑时核实空闲；禁止回退到 8780--8830。独占 users / Episode / 待重核根，remember=false，不落密钥。
- 保留原始回答与 trace，闭环核生产身份、冻结输入和进程/锁；不合 main、不部署、不覆盖旧样本。

## 仍需完成

授权及顺序修订 -> 补齐独占启动/冻结/收尾控制，并先完成判定器的旧失败阳性对照 -> 三题各一次 -> 逐项审计 -> #75 独立终审。正文保留的语义审计不能由 activity counts 替代；没有发生迟到回包时，该自然分支标 NOT_EXERCISED，严格传输探针证据单列。单位错位仍归 #852，不能在批内顺手修后重跑刷绿。

本轮未新增通用脚本：提取与哈希使用已有入口；待授权 JSON 只是执行协议草案，不具备授权或启动能力。
