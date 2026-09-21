# #845 历史控制边界返修

## 这个分支做什么
叠在#833之上修H-01：引用不能恢复历史权限；不合main、不部署。

## 决策与被否方案
- 复用user_task来源分区；否另写引号正则/清空全部历史，原文仍保留。
- 历史helper、通用追问回填、截止投影一起保护；否只验材料编译器。
- 显式续问保窗口/截止/local_only；省略式合同丢失另列H-02，不用局部绿覆盖。
- 变异只改进程内函数并finally恢复；否反复编辑冻结树。背景见`../2026-09-21-history-control-boundary-repair.md`。

## 当前状态
WIP #845，源码`fix/history-forward-boundary-0921@d91aff9d8437fe903f3e643b65d4805aa4cf243c`已推且clean；父#833仍7edfe24e7，未动。交接/证据集中#838文档枝，源码SHA不因归档移动。
H-01受测范围已修；整体历史仍CHANGES_REQUIRED。H-02正常版2反例仍红：合法省略续问保历史与截止，却material_contract=None，授权含web_search/web_fetch；只检查工具登记，未执行IO。不要等独立审核替代修这个缺口。

## 未验证 / 已知边界
本revision未跑完整Python、前端/E2E/registry全叶；530定向绿不是合入门禁。历史原四自然题仍not_passed，三领域独立终审仍缺。本轮未重开外审；runtime/财务只保原候选，联合树/#841未验。无合并/8792部署/生产回填/清树授权；#814正式收据线不接管。

## 下一步
从新包`frozen-regressions/adjacent-unresolved.txt`的两红例修H-02：可信用户基底的权限上限须随历史意图同步，不能从旧助手话/无条件复制合同猜授权。新SHA重验正负例与执行前上限；新任务/取消/material_only不得被旧合同污染。完整门禁与独立审查另计，不自动重试付费通道。

## 踩过的坑
误编辑无boundary后缀的原候选已精确撤回并验clean。替身缺relation_path、local能力白名单过窄均是夹具错误。首版patch.object恢复__code__失败，输出不是有效收据，v2/frozen已另验。单撤resolution保护原39例未红，补2例后抓到1F。

## 已验证
固定d91干净树530P=168+169+193（内含新41例），全仓Ruff/diff-check通过；五变异24/15/6/1/4断言红、0夹具错、源码前后哈希相同。H-01夹具禁并计数socket/DuckDB连接，离线模型/知识替身；既有回归用临时DB不外推零DB。
证据`docs/verification/2026-09-21-research-tail-forward/history-boundary-repair-01/README.md`；旧三包不改。邻接2F单列，不以runner exit0洗绿。
