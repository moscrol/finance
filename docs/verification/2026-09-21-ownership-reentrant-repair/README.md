# O-K3-001：pytest 调用级收据归属修复

## 结论与授权

用户在 K3 归属审查收口后回复「继续」，本轮承接 #814 的 O-K3-001 修复；没有新增模型会话、扩额、合 main、部署、生产回填、真实工作树删除或 Arena 接管。

- 修复提交：`a092a021c3d7d978c4dfd9551e74aa984a523f18`，已推 #814。
- 修改仅 `conftest.py` 与 `tests/test_main_gate_receipt.py`；父版本 `54913deb9707b4631c110b7bce38bf5db024b980`。
- **作者工程验证通过**：本分支干净固定源码 Python 全量 **11963P/85S/2X/0F/17 warnings**，全仓 Ruff 通过，真实 shell gate exit 0，前后 SHA/干净状态一致。此处 P=通过，S=跳过，X=预期失败；2X来自 JUnit/终端，不是收据 JSON 字段。
- **独立完成度没有升级**：旧 v3 K3 Spec/Quality 均未终审；本次没有追加审查。O-K3-001 在新代码上经作者修复与验证，不等于独立接受；旧 `47530e20` 仍是已知有缺陷的历史对象。
- **未做最新 main 合流/三单新组合**，未跑本修复的 frontend/E2E/registry 独立叶。11963 与旧组合 12068 属于不同对象/范围，不能作增减回归比较。

## 修复原理及选择

环境中的 owner PID 仍阻隔继承父路径的子进程；额外把 `(PID, 认领路径)` 存在本次 pytest `Config.stash`（调用配置的私有存储）里。另一层 `pytest.main()` 没有本次 Config 的凭据，即使 PID/target 相同也不能写父文件。用 `Config.add_cleanup` 释放自己认领的环境状态，正常退出与配置失败均释放；顺序调用可再次认领，继承的 owner 不由本次清理。

否决只比较 target、只使用唯一/不可覆盖文件、或同 PID 自动重领。它们均不能证明第一位写者属于外层调用。既有树身份、实际退出码、不可覆盖写入、latest 仅导航保持不变。此机制防合作执行中的误归属，不是对恶意测试代码/同用户写者的安全沙箱，也不承诺线程并发调用 pytest 的支持。

## 证据顺序

| 证据 | 结果与边界 |
|---|---|
| `red-new/` → `green-new/` | 首批同一9例：旧码6F/3P，修后9P；记录当时工作区哈希，dirty迭代不是提交收据。 |
| `focused/` → `focused-final/` | 初版相关65P，扩展后四模块71P；最终新增15例。 |
| `old-source-final-tests/` | 精确旧生产代码 + 最终已提交测试，隔离玩具仓15例11F/4P；不是把旧工作树回退。 |
| `mutations/` + `mutation-results.json` | 同一15例基线/还原各15P；去Config证明7F、去cleanup4F、允许同PID重领6F。三个变异均抓住指定反例，均无装置error。源码树不变。 |
| `exact-source-reproduction/` | 从a092复制完整原环境契约及hook/shell/helper；子进程对照及同进程复验都正确记录外层target/1P，无不可覆盖告警。沿用旧复現装置的派生脚本，改动清单见`reproducer-provenance.json`；旧装置/原件未改。 |
| `clean-source-full/` | 完整真实shell gate，1784.292s；pytest 1778.47s。所有输出/收据在证据根，`--basetemp`和JUnit定向隔离。 |
| `source-readback/`, `source-compatibility/` | gate仅收据模式及通用条件校验均exit0，确切a092与原树；不是latest。 |
| `source-gate-qc.json` | 唯一收据、JUnit逐项、终端总数对账通过。JUnit12050个case，含11963P/85S/2X。 |

唯一全量收据：`clean-source-full/receipts/gate-QQdiL9Bn/pytest.json`。运行解释器始终 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`；没有把宿主Python拿来跑pytest/ruff。脚本使用最小环境与`PYTHONDONTWRITEBYTECODE=1`；正式回归中合成仓的环境契约是小夹具，额外精确源码复验复制完整契约以排除该差别。

shell本来只保留pytest末15行，`stdout.log`不是全量测试输出；JUnit保留逐项结果但也不是完整stdout。全量期间一次`sample`只观测本次进程调用栈，未修改进程；保留诊断。首尾净树只证明两个时点，不是OS级不可变证明。

## 归档、基线与后续

归档：协调树 `docs/verification/2026-09-21-ownership-reentrant-repair/`，manifest列成员/字节/哈希/来源。`.py/.sh/.log`仅加`.txt`后缀，字节不变；DB/Git对象/缓存/测试临时大树/latest导航排除。有限装置随证据保全；长期守卫是正式pytest回归，不另装调度器。

`previous-archives.json`确认五代旧档（不含manifest各30/30/86/26/450）与已提交原件逐字节一致。`preseal-state.json`记录v3作者/Spec/Quality仍净树47530e20，#813未改；源码a092与协调树亦净。06:02Z远端main已到`c615adbd2f861e23f2c8d03631833f98b3ae5aba`，是其他会话变化；未把本轮结果转签main。

通用模式已回写独占harness分支的BUILD §5/KIT，提交`9f1c80b0b681e6fce89fe118377a67387f756e9a`推PR14；共享主树未碰。后续需明确集成基线、冻结新组合并重跑全部叶；新增独立审查会话/预算与合并、部署、回填、删树分别获授权。文档提交不继承a092源码收据。
