## K3 独立审查 · e2 组（C1–C3）stage=explore 终稿

**状态：未交付探针——闭幕指令在全部预算付诸读代码后到达，任何写文件轮均未发生。不签候选 PASS，未运行任何 pytest。**

### 已完成的静态检查（只读，实际读过）

- `intelligence/services/material_delivery.py`（全 284 行）
- `intelligence/services/material_contract.py`（全 206 行）
- `intelligence/services/research_contract.py` 第 1020–1199 行（`__post_init__` 的 material_only/local_only 校验、`from_dict`）
- `intelligence/services/episode_factory.py` 第 655–850 行（槽冻结、能力收窄）
- `intelligence/services/episode_verifier.py` 第 200–309 行（legal_gap 分流）
- 作者测试 `tests/test_e2_local_question_delivery.py`（全 289 行，仅用于学 API，未复制）

### 静态核对结论（仅读码，未经探针验证）

- **C1**：`question_sections`/`question_body`（material_delivery.py:151–190）对重复小节返回 `""`（`len(blocks)!=1`）、剔除引用/代码块、纯标题与「待补」等同形视为缺正文；`material_delivery_missing_outputs`（:212–228）要求绑定齐全**且**正文有效，来源绑定不掩盖正文缺失——与主张方向一致。
- **C2**：`episode_verifier.py:239–257`，`legal_gap` 仅在 `grounding_scope=="material_only"` 时结清；local_only 缺口回落 `REQUIRED_OUTPUT_GAP`→partial。`material_input_output_ids`（material_delivery.py:52–60）对 local_only 返回空集，零读取豁免不外溢。`_LOCAL_ONLY_RULES`/payload 措辞不含 legal_gap。
- **C3**：`episode_factory.py:713–733` 仅在 `local_only` 且 `material.questions` 非空时冻结 `answer_{qid}` 槽（必需、grounding="evidence"）；未编号本地题与 full 模式不走此分支。`research_contract.py:1125–1138` 恢复校验以「已有 answer_q* 槽」为判据，旧 direct_answer 形状不误伤。

### 疑点（均未经探针验证，列给下一场）

1. **重复题号可达性（C1/C3 边界）**：`material_contract.py:149` `compile_material_contract` 建题不重号检查和 `from_dict:105` 的拒收不对称；若 `TopLevelRegions.question_ids` 可产出重复 qid（如用户写「1. … 1. …」），`episode_factory` 的 `material_descriptions` dict 会静默塌缩一题。**`user_task.py` 的 question_ids 生成未读，可达性未确认——最高优先级补查。**
2. `_HEADER_RE` 接受 `q0`/跳号/中文「第N题」，边界题号（q0、缺号 3/5、dup）未探。
3. local_only 下 `binding.gap` 非空时走 gap 分支先于证据验收（verifier:238 起），方向偏保守未见泄漏，但混绑（gap+hashes）形状未探。
4. 恢复时多余 stale `answer_q7` 等不在当前 questions 内的槽不被拒收，疑似良性，未探。

### 未完成覆盖与限制（必须明确标记）

- **写盘门未达成**：`work/e2/probes/test_reviewer.py`、`work/e2/probes/test_positive_control.py`、`work/e2/EXPLORE.md` **均未写入**，自造探针数为 0。下一会话必须补写正控探针（含 `assert 1 == 2`，记 expected_positive_control/probe_bug）后再跑。
- `episode_semantic_verifier.py`（6720 行）实现未读；`episode_verifier.py` 仅读 200–309 段；`research_contract.py` 其余 1700+ 行未读；IO 纯度（io_effect 冻结 scope）实现路径未核。
- `.git` 按要求未访问；未运行任何 pytest；不构成候选 PASS。

```json
{"stage":"explore","group":"e2","revision":"8eac9b3b55c563b1eb3be58686fcc0918464f69a","baseline":"b59d6eed0356ae093b52bd291ab328628de8790e","complete":true,"artifacts":[],"suspected_issues":["C1/C3: compile_material_contract 未查重复 qid 与 from_dict 拒收不对称，episode_factory material_descriptions 可能静默塌缩重复题号（可达性依赖未读的 user_task.question_ids，未验证）","C1: 边界题号 q0/跳号/重复小节与 memo 计数探针未执行","C2: io_effect 冻结 scope 的完整执行路径未核读","C3: 恢复时 questions 变更(续轮加题)与 stale answer_q 槽行为未探"],"limits":["探针文件与 EXPLORE.md 未落盘：闭幕在写盘轮前到达，自造探针 0 条，下一场必须补写","episode_semantic_verifier.py 未读；research_contract.py/episode_verifier.py 仅部分阅读","未运行任何 pytest；静态读码一致方向不构成候选 PASS",".git 未访问（按指令）"]}
```
