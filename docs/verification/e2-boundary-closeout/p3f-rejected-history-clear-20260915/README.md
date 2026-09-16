# P3f 历史清空候选：作者反证与撤回

**状态：候选被否，未进入独立 QC；没有新的 P3f 应用修复。**
应用与原 P3d 测试已逐字节恢复到 `6f490f73`；新增两条合法输入正例保留在
`intelligence/tests/test_e2_controller_material_history.py`。正式 T2→T3/Knevo 未运行。

## 发现顺序与读数

| 实验 | 结果 | 结论边界 |
|---|---|---|
| 候选原定向三文件 | 148P；dirty receipt | 旧断言绿，不覆盖合法跨轮材料；无全进程禁止 IO 计数 |
| 候选相邻三文件 | 206P；dirty receipt | 与148P重叠，不相加，不是独立QC或产品验收 |
| 新增两条真实入口正例，候选代码 | **2F**；禁止尝试0，pytest/shell exit1 | 一条丢材料身份，一条缺材料不澄清；见 candidate 原日志 |
| 同一两条正例，恢复原代码 | **2P**；禁止尝试0，pytest/shell exit0 | 排除夹具本身导致退步，不证明原代码已安全过滤历史 |
| 恢复后四文件定向回归 | **150P**；禁止尝试0，pytest/shell exit0 | 新正例 + 原 P3d/P3e/controller 测试；不是全仓测试 |
| 归档检查器测试 | 15P，exit0 | 合成Git库故障变体；不套用上述IO隔离计数 |

首次148P之前的意图夹具失败未保留完整日志，不能事后补造计数。其修正是 controller
输入取持久化的 `intent`，不是 controller 返回的带本轮继承标记的 `inherited`。
早期148P/206P收据在 `candidate-earlier-*-receipt.json`，不是撤回后的读数。

## 被否方案

候选在 controller 前复用 `split_user_message` / `compile_material_contract`，明确
`material_only` 时传 `context=""`、`previous_intent=None`、`previous_turn_id=None`。
字典判断复用本身没有问题，但这不是按来源过滤：

1. 上轮用户材料应有前提资格；清空后 `referenced_material_ids` 由预期
   `m-67f3ee73e3` 变为空元组。
2. `decide_turn` 将空串当旧调用方的“未知上下文”，不等于真实入口的“已知无材料”。
   缺材料题错误进入 research，而不是先 clarify。
3. 源码另见兼容 controller 回落仍使用原 inherited intent；本次两条探针未验证该旁路，
   不能凭静态发现声称已修或已复现。

只把空串改成空历史标记能修第2条，但仍丢第1条；全部放行历史则保留外部先验问题。
下一片须区分用户材料、助手历史判断、缺失/截断状态，并复用同一来源投影供 controller、
TaskFrame 与兼容路径消费。D7 的同题来源资格、旧答纠错可见性和权限继承不能被一个
布尔清空开关替代；本目录没有实现或认证该方案。

## 证据及复现

- `rejected-candidate.diff`：相对 `6f490f73` 的原候选，两处修改；只供反证复现，不重新应用到工作树。
- `source-state.json`：恢复后源文件哈希；`test_e2_controller_material_history.py.txt` 为当次测试原件。
- `launcher.py.txt`：作者计数启动器。模型返回显式本地桩；真实 run_turn→decide_turn，
  在 controller 返回后立即停，不运行 Episode、adapter 或交付副作用。
- 启动器以 `E2_TEST_ROOT`、`E2_TEST_EVIDENCE`、`E2_TEST_NAME` 定位；例如在隔离检出中执行
  `python <launcher.py.txt> -q intelligence/tests/test_e2_controller_material_history.py`。
  使用主树 workbench venv 解释器。临时根须 resolve；同名重跑会覆盖收据，另取 NAME。
- Python audit 拦网络、子进程、生产路径；另拦 native DuckDB connect。
  **不是操作系统沙箱**，也不证明 native 扩展全部 IO 已覆盖。
- 所有归档原件逐字节保留；`.py` 改名 `.py.txt` 只为避免历史文件被当应用源码。

## P3e 归档补正的附带证据

`archive-before-check.json` 对 `6f490f73` 明确拒绝：4项文件未入Git，2项未列入清单。
`archive-after-check.json` 对 `e5fab415` 完整通过：26项清单=26个Git文件，哈希全符。
由 `scripts/check_evidence_archive.py` 读取固定提交对象，而非工作目录验证。
这不重判 P3e 独立报告，首次审查器误拒41次的历史仍保留。

本目录清单仅排除自身。提交后从仓根验证：

```bash
python3 scripts/check_evidence_archive.py \
  docs/verification/e2-boundary-closeout/p3f-rejected-history-clear-20260915 \
  --revision HEAD
```
