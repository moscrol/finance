# Knevo 盘面研究维度 Implementation Plan

> 本会话按已授权设计逐项执行，再用 code-review 的两个独立轴评审。

**Goal:** 默认盘面研究仍提供总览、主线和风险视角，交付由完整用户原问决定。

**Architecture:** 在既有 TaskFrame 装配处声明研究维度；Episode factory 沿用 RequiredOutput 的可选语义，模型输入将这三项移动到研究维度。权限、取证与检查保持原运行路径。

**Tech Stack:** Python dataclass、既有 Episode JSON 协议、pytest；使用本树 `.venv-workbench/bin/python`。

## 1. 区分默认要求与研究维度

修改 `intelligence/services/task_frame.py`，集中提供：

```python
def research_dimensions_for(question_type: str) -> tuple[str, ...]:
    if question_type == "dated_market_review":
        return ("market_summary", "mainline_structure", "risk_signals")
    return ()
```

默认 dated 产出改为 `("direct_assessment", "evidence_boundary")`。既有显式语义分支与 `extra` 合并保留；rebase 已使用同一默认函数，不能再加第二份名单。

- [ ] 修改对应旧默认断言；增加原问、重建题型和明确必需项的回归。
- [ ] 跑 `.venv-workbench/bin/python -m pytest -q intelligence/tests/test_task_frame.py`。

## 2. 沿真实 Episode 接入研究维度

修改 `intelligence/services/episode_factory.py`：`_required_output_ids` 合并 `frame.required_outputs` 与 `research_dimensions_for(frame.question_type)`。`RequiredOutput.required` 继续原规则，并增加：

```python
output_id not in research_dimensions_for(frame.question_type)
or output_id in frame.required_outputs
```

材料编号重写仍在原位置；历史研究不挂默认盘面维度。修改 `intelligence/services/episode_protocol.py`，将合同中非必需的这三项移动到 `research_dimensions`，说明内部自检、相关性、反证、用户要求优先、使用时原证据检查仍生效。两处使用同一维度函数，不维护 id 白名单。

- [ ] 用真实输入及终稿验证路径验证维度送达、可省略、显式要求不可省略及伪证据拒收。
- [ ] 对照原基座保留取证计划、授权、时间及预算；编号材料与其他题型形状不变。
- [ ] 跑 task-frame、factory、protocol、agent-episode、材料与市场回答相关回归；修正实际失败再复跑。

## 3. 验证、评审与交接

- [ ] `git diff --check` 与 `.venv-workbench/bin/python -m ruff check .`。
- [ ] pathspec 提交本次文件；在干净固定提交跑 `scripts/run_main_gate.sh`，显式 basetemp，收据根置于 `.finance-runtime/answer-quality-closeout-1007/`。
- [ ] 用 `scripts/check_test_receipt.py <本轮收据> --require-full-scope` 自证全量；原件与代码 SHA 单独记录。
- [ ] code-review 的 Standards / Spec 两轴审阅本次固定提交及设计，处理可复现缺陷。
- [ ] 按实际动作更新 #66 主交接和日期快照，普通推送原 PR；CI 绑定最新准确 SHA。主干合入、生产切换与正式盲评仍按各自授权执行。
