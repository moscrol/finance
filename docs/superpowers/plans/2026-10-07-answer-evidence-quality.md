# 回答证据与修订保真 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. 每个实现使用新上下文；Spec 通过后做质量复核。

**Goal:** 修复已实测的数据零化、句数弃修订、反方标签截断，并用原失败样本核真实回答。

**Architecture:** 在现有数据文本生产、修订接纳、逐卡投影三处保存语义。所有核验、权限、预算及原始证据身份继续由既有流程承担。

**Tech Stack:** Python 3.12、DuckDB、现有 pytest 与 Episode（Workbench 对话研究循环）。

---

### Task 1: 主线涨停计数缺失保真

**Files:** `intelligence/services/ask_blocks.py`；`intelligence/tests/test_mainline_history_scope.py`。

- [ ] 在现有 `scope_db` 夹具对截止日同一行分别写 `NULL`、`0`、`7`，通过真实 `render` 调用断言未知、零、7 可区别：
  ```python
  @pytest.mark.parametrize('count,expected', [(None, '涨停未提供'), (0, '涨停0'), (7, '涨停7')])
  def test_limit_up_count_missing_is_not_zero(scope_db, count, expected):
      with duckdb.connect(str(scope_db)) as con:
          con.execute('update fact_mainline_sector_daily set limit_up_count=? where sector_ts_code=?', [count, 'current2'])
      line = next(line for line in render(scope_db).splitlines() if 'current2(' in line)
      assert expected in line
      if count is None:
          assert '涨停0' not in line
  ```
- [ ] `.venv-workbench/bin/python -m pytest -q intelligence/tests/test_mainline_history_scope.py`；旧版未知组必须红，保留输出。
- [ ] 将原 `limit_up_count or 0` 改成 `limit_up_count if limit_up_count is not None else '未提供'`，不改其它字段或查询。
- [ ] 复验上面命令及 `intelligence/tests/test_ask_compose.py`，检查 `block_lines_to_evidence` 的逐卡文本仍区分缺失/零。
- [ ] 用 pathspec 提交这两个文件；独立 Spec → Standards 通过后进入下一任务。

### Task 2: 补查候选按核验接纳

**Files:** `intelligence/runtime/continuous_turn_adapter.py`；`intelligence/tests/test_continuous_turn_adapter.py`。

- [ ] 基于现有 `test_backfill_turn_rejects_candidate_that_adds_sentences` 和邻接真实 `CallbackEpisodeSession` 用例增加有证据的较长候选：第二句解释新市场证据并绑定原输出，断言它到达结构/语义核验并成为公开回答。不能只测私有方法或将任意长稿直接批准。
- [ ] 旧版运行上述新用例，确认实际句数早退导致失败；日志留树外。
- [ ] 删除 `_resume_for_backfill` 的下面早退以及仅用于它的 import（若全文件不再使用）：
  ```python
  if draft_sentence_count(candidate.draft) > draft_sentence_count(outcome.draft):
      return None
  ```
  保留后续 `_structural_verifier` 与上层语义/公开交付调用，保存失败和空稿回退分支原样。
- [ ] 将旧测试改为按实际证据资格区分候选：有据可解释；无依据数值按既有策略删除/待核，不允许悄悄变成有依据；保存失败仍传到产品失败。另测字少但无依据也进入同一核验。默认判官off的mark模式仍可能completed，应留边界；无效绑定/错误证据类型继续拒收。不得新增句式、金融词或数值白名单。
- [ ] `.venv-workbench/bin/python -m pytest -q intelligence/tests/test_continuous_turn_adapter.py`，保存完整本文件结果；用 pathspec 提交，再独立双轴复核。

### Task 3: 每张检索卡携带立场

**Files:** `intelligence/services/evidence_search.py`；视真实投影决定是否修改 `intelligence/services/agent_research.py`、`intelligence/services/agent_runtime.py`、`intelligence/services/prior_evidence.py`；同步 `intelligence/services/research_tool_registry.py` 中旧立场说明；测试 `intelligence/tests/test_evidence_search.py`、`intelligence/tests/test_research_harness.py` 及需要的旧证据恢复测试。

- [ ] 在既有窄/宽/反方检索夹具构造超过现有观察窗的支持文本，将反方卡放最后。通过真实 Episode 工具结果模型投影检查末卡的检索方向，而非只检查工具原件总文本。
- [ ] 旧代码运行并见反方标签缺失，保留红结果与原观察上限。
- [ ] 最小实现将真实 `stance` 保存在逐卡投影可见位置，采用独立可选元数据或明确的逐卡检索方向前缀；若复用文本须明确为检索分桶，不能赋予新来源强度。原 WikiHit `content_hash`、日期、来源保留。不得用 `supports`/`contradicts` 输出ID字段偷存检索标签。旧卡无标签兼容。
- [ ] 实际返回的支持/反方两桶以及长观察末卡都验证；不扩交付集合。所有标签仅说明检索方向。模型可见原正文、来源与日期仍存在，已有 ordinal/hash 接纳和证据资格不变。若新增字段，验证旧普通卡有/无历史元数据的两种既有形状、完整新卡均可恢复；未知字段/无效类型仍拒绝。
- [ ] 实际投影邻近测试全部跑绿，pathspec 提交；独立 Spec → Standards 通过。

### Task 4: 集成与真实内容核验

- [ ] 根 agent 核所有三任务与原始错误证据一一对应，更新产品门文档并验证误把未排序切片当全市场排名是否仍存在。
- [ ] 按准确最终 revision 跑既有 Python 全量、ruff、registry 与前端六项，收据自证完整收集；不可借前一版或收窄结果。
- [ ] 开 GitHub PR 并 attach；所有条件叶通过后按已授权发布流程交付或保留待合并，原生产不得提前切换。
- [ ] 真实入口只跑固定首次样本，固定数据和实际模型身份，首次输出留原件；逐项审缺值/排名/资金判断/修订送达，不以结构 completed 代签正确。不改问题挑稿，不重跑旧 CLOSED 批次。
- [ ] 承接树外台账，完工再写准确交接；剩余未改善项明确保留。
