# Knevo 盘面研究维度 Implementation Plan

> 本会话按已授权设计逐项执行，再用 code-review 的两个独立轴评审。

**Goal:** 默认盘面研究仍提供总览、主线和风险视角，交付由完整用户原问决定。

**Architecture:** 在既有 TaskFrame 装配处声明研究维度；Episode factory 沿用 RequiredOutput 的可选语义，模型输入将这三项移动到研究维度。权限、取证与检查保持原运行路径。

**Tech Stack:** Python dataclass、既有 Episode JSON 协议、pytest；使用本树 `.venv-workbench/bin/python`。

## 1. 区分默认要求与研究维度

修改 `intelligence/services/task_frame.py`，集中提供：

```python
def research_dimensions_for(frame: TaskFrame) -> tuple[str, ...]:
    if frame.question_type == "dated_market_review" and frame.history_intent is None:
        return ("market_summary", "mainline_structure", "risk_signals")
    return ()
```

默认 dated 产出改为 `("direct_assessment", "evidence_boundary")`。既有显式语义分支与 `extra` 合并保留；rebase 已使用同一默认函数，不能再加第二份名单。
`_user_goal` 在既有语义分支之后，对 dated 默认返回本题 `question.strip()`，避免分类器通用目标扩大任务。
复审发现 id 集合不足以区分默认项与同名调用者要求：补 `TaskFrame.required_output_additions`，由实际调用参数写入，rebase 保留同名要求，`from_dict` 拒绝不合法或不在最终要求内的记录。空值不进旧形状/哈希，对齐模型无写权；加入默认同名冲突及序列化恢复的拒漏反例。
rebase 转入 dated 时使用已有 `_GENERIC_GOALS` 区分占位目标与有内容的上下文目标；前者调用 `_user_goal` 恢复原问，后者保留。用真实 legacy Controller 的 `route_id` 回复验证与直接构建一致。
全仓暴露继承污染：`rebase_task_frame` 用 `inherited_required_outputs` 接活动旧合同，Controller 的 intent 继承调用改用此参数；当前明确子任务覆盖旧报告，本轮 `required_outputs` 新要求仍保留。原 benchmark 冻结断言保持不动，增加两条来源同时存在的正反控制。
盘点全部真实 rebase 调用者：query_resolution、Controller decision/intent、TurnControlCore legacy intent。legacy 的 QueryEnvelope 不再重复填旧 required_outputs，rebase 统一走继承参数。基础项取 `explicit_outputs or inherited_required_outputs or _clean_outputs(inherited_outputs, canonical_outputs)`，最后与 additions 合并；验证继续/详细续问/指代续问完整沿用旧合同、明确追问收窄以及无 frame 兼容入口。

- [x] 修改对应旧默认断言；增加原问、重建题型和明确必需项的回归。
- [x] 跑 `.venv-workbench/bin/python -m pytest -q intelligence/tests/test_task_frame.py`。

## 2. 沿真实 Episode 接入研究维度

修改 `intelligence/services/episode_factory.py`：`_required_output_ids` 合并 `frame.required_outputs` 与 `research_dimensions_for(frame)`。`RequiredOutput.required` 继续原规则，并增加：

```python
output_id not in research_dimensions_for(frame)
or output_id in frame.required_outputs
```

材料编号重写仍在原位置；历史研究不挂默认盘面维度。修改 `intelligence/services/episode_protocol.py`，将合同中非必需的这三项移动到 `research_dimensions`，说明内部自检、相关性、反证、用户要求优先、使用时原证据检查仍生效。两处使用同一维度函数，不维护 id 白名单。

- [x] 用真实输入及终稿验证路径验证维度送达、可省略、显式要求不可省略及伪证据拒收。
- [x] 对照原基座保留取证计划、授权、时间及预算；编号材料与其他题型形状不变。
- [x] 跑 task-frame、factory、protocol、agent-episode、材料与市场回答相关回归；修正实际失败再复跑。

## 3. 验证、评审与交接

- [x] `git diff --check` 与 `.venv-workbench/bin/python -m ruff check .`。
- [ ] pathspec 提交本次文件；在干净固定提交跑 `scripts/run_main_gate.sh`，显式 basetemp，收据根置于 `.finance-runtime/answer-quality-closeout-1007/`。
- [ ] 用 `scripts/check_test_receipt.py <本轮收据> --require-full-scope` 自证全量；原件与代码 SHA 单独记录。
- [ ] code-review 的 Standards / Spec 两轴审阅本次固定提交及设计，处理可复现缺陷。
- [ ] 按实际动作更新 #66 主交接和日期快照，普通推送原 PR；CI 绑定最新准确 SHA。主干合入、生产切换与正式盲评仍按各自授权执行。
