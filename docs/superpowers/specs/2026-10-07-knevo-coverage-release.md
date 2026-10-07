# Knevo 研究维度独立发布

用户授权：2026-10-07「你先把优化上线后再对比」。本次允许完成这个结构优化的 GitHub 合入及 8792 发布，后续实际问答对照仍须保留版本、数据、模型与成本记录。

## 发布范围

从最新 `origin/main@ea217633ceeaceeb41d3b3f30fa58708fe14ecc9` 组装原已审代码 `a5feb32b59096ab5357dbc96255191a88c50c534` 的结构片，差分区间 `7212d71c9..a5feb32b5`。只包含默认盘面研究维度、调用者要求来源、活动合同继承及 Frame/intent 一致性；原 #66 的市场数字修复、历史证据续用、日期范围及正文过滤另留草稿，不作为本次发布依赖。

实现合同见 [研究维度设计](2026-10-07-knevo-market-research-dimensions-design.md)。总览、主线、风险按问题相关性内部自检，仍供给有据视角与反证；当前明确子任务优先、普通继续完整承接。来源身份、信息截止、工具权限、根预算及取消沿原路径。

## 发布验收

- 在实际发布环境跑准确干净提交的 ruff + 完整 pytest；自证 collected 与结果对账、版本、解释器、依赖指纹。局部或旧分支收据不移签。
- 独立 Standards / Spec 评审这个 main 上的有效增量；正常与 legacy 三轮、同名新增、材料编号、原 benchmark 红灯和未放松的来源/权限正反控制。
- GitHub 的 python / frontend / e2e / registry-check / workbench-check 均通过准确 PR head 后才合入。该片不触发 data-quality 条件路径。
- 合入后从最新 main 建只读代码快照，解释器补齐，再按既有版本切换/回滚流程上线8792。记录切前代码、监听进程及健康原件；保留原快照以回滚。
- 切后 readiness 全部通过，health 的实际 source_revision 为新版本、source_dirty=false、code_matches_repo=true；真实会话源码/用户/运行身份正确，结构片实际到达作者。
- GitHub→Gitea 备份确认新 main。合入、部署、原答卷质量和新对照结论分别记录。

## 环境与成立条件

旧生产共享环境 HTTPX0.25.2 与依赖锁0.28.1不一致，workspace doctor 已实测拒绝。新版本使用独立 `~/.finance-runtime/venvs/workbench-locked-20261007`，由已锁定的受测环境原生 APFS 克隆，解释器及依赖校验后用于发布。旧环境及快照仍可回滚；不绕过依赖门禁，不改共享环境。

这份发布不认证自然回答已比Pi更好。先按本次用户顺序上线，再同模型、同数据时点对照完整答卷，并检查上下文消费与记忆效果。
