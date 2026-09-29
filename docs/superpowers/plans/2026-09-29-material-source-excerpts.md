# Material Source Excerpts Implementation Plan

> 用户授权继续；在当前隔离工作树内按步骤实现和验证，完成后执行独立code-review。

**Goal:** 验证作者选择原文片段能否减少无意义抄录失败，同时保留全部来源边界。

**Architecture:** 在material_answer_authoring内共享目录生成和格式选择，将v2 sources精确展开为v1输入，复用现有编译/验证。不新增研究工具、模型调用或持久化合同。

**Tech Stack:** Python 3.12；主树.venv-workbench；pytest/现有Workbench probe。

## 步骤

- [ ] `intelligence/tests/test_material_source_excerpts.py`先写原文引号与多行选段往返测试、假编号/跨M-H/历史多选反例和schema一致性；预期当前缺v2支持为红。
  核心断言：`validate_episode_finish(v2, context=context, evidence=()) == validate_episode_finish(v1, context=context, evidence=())`，v1.quote必须是选中原文，另断言raw和contract未变。
- [ ] `intelligence/services/material_answer_authoring.py`生成`{parent+'.X'+str(i): {'ref':parent, 'quote':raw_slice}}`目录；`raw_slice`来自`claim_sentences(item.text)`。作者仍挑选字符串编号，未知编号抛`material_source_violation`，映射只复制原ref/quote。
- [ ] payload/schema以默认关闭的环境变量选择v2，compiler显式兼容两版；复用v1的来源、历史及格式错误分类。不改其他运行时预算/权限逻辑。
- [ ] 主venv跑新增文件、test_material_answer_authoring、test_material_quote_recovery、test_material_claim_rendering与episode协议相关回归，Ruff；独立规格/代码审查修回后再冻结代码。
- [ ] 固定提交启动隔离服务，按spec四次首发顺序记录原题hash、实际模型、token、非法动作、公开答卷；独立内容裁决，失败不重抽。
- [ ] 只有达到预注册保留标准才保留实验实现，否则撤掉运行时代码，留原证据。最终适配范围检查、更新报告/PR/交接，保持WIP。
