# 两批发布与第二批文档工具合流

## 背景与授权

10-10 用户已选择第一批“合并并切换”“开一张合集 PR”，第二批“接着第一批一起做”，并授权清理已被取代的 PR / 分支及已核可拆工作树。10-11 接手续做第二批；不扩大到活动分支、未通过的金融质量实验、生产回填或仓库可见性变更。

第一批经 [#84](https://github.com/moscrol/finance/pull/84) 合入并部署 `8b01812bd1837b4bbdd52ed8ba2adced320100a7`。第二批不更换 8792，生产快照 `8b01812bd183` 和回滚锚 `6c1d9f5d4478` 均保留锁定。L2 夜跑已单独使用修正后的 `f0865392500e289d448f8ecaca6eb92770d23b38`，原生成根及解释器仍依赖 `ffe1c60d84da`，不得随清理删除。

## 按发现顺序

1. 接手时独占树 `fwp-wt-release-wave2-1010` / `release/docs-tools-wave2-1010` 干净，合流头 `a20825451ac8d383b8ca8e59260f99a13ac72cdc`；七条来源线已完成普通 merge，无进行中冲突。
2. 重新 fetch 后基线仍是第一批 main；GitHub 六张来源 PR 的 head 未变，main 保护保持 strict、管理员受约束，必需 `workbench-check` / `registry-check`，禁止强推与删除。
3. #63 与第一批 #67 的 AGENTS 冲突已保留 staged-credentials 凭据扫描边界及 hook 配置事实指针，不覆盖任一方意图。
4. #61 增加当前时点勘误：身份读取修复已经 #70 合入部署；当前 `model_admission.py` 与旧 d5、05b 候选都不同；10-06 具名备份文件已不存在。旧原始收据不改写，也不移签为当前完整验收。
5. L2 旧无条件清理记录增加 superseded 标记，权威需求指向成功后清理修正文档。#73 增加 #74 接替指针，不翻案旧首答。
6. 从 #66/#78/#81 精确提交保全六份日期文档，不合入这些旧分支的整套代码；旧“当前”“未部署”“下一步”仅属于原文记录时点。
7. 第一批台账补记健康、门禁、探针及数据不就绪边界；部署流程修正 venv 指针。第二批须有自己的候选和实际 main 收据，不能借第一批数字。

## 第二批来源

| 来源 | 固定 head | 本次范围 |
| --- | --- | --- |
| #63 | `597f2ad18b77c2904ff8a870ec854d35fff45da6` | hook / 分支保护事实文档 |
| #49 | `a136e41e62bc20c1c9debfce0bf9901d309f2ff1` | 工作树父目录引用误阻断 |
| #53 | `4594192cc5ba5a2706779b491b4be13a5c12b3b2` | shell 展开边界解析；堆叠于 #49 |
| #51 | `a8fe098a83ddb6cd7e99004d24dbb20c6693c933` | 全量收据拒绝位置参数收窄 |
| #73 | `d49aa8576b19c188ea833d8f1c0982f1b03bbd63` | 部署与有界质量核验历史 |
| #61 | `ca185cca5965b3b8878bc7ce4c57e1030661c5fc` | post59 部署证据及身份补查 |
| L2 | `f754b349d` | 成功后清理、失败保留及日期/软链安全 |

## 保全文档与接替

下列正文按原提交导入，仅补历史时点提示；不改其失败结论或声称完成其中待办。

| 原 PR / head | 文档 | 后续接替 |
| --- | --- | --- |
| #78 / `a52bf2676` | [回答资格根因](2026-10-08-answer-qualification-root-cause.md) | #80 实现、#82 后续成稿合同；全文质量另验 |
| #81 / `7c86d613f` | [同源结果与唯一首答](2026-10-08-owned-result-delivery-and-first-answer.md) | #80 部署记录、#82 后续；原首答仍 NOT_PASSED |
| #66 / `afea1daf4` | [离线内容审计](2026-10-06-answer-quality-offline-content-audit.md) | #68/#70/#80/#82 分项承接，不声明整枝等价 |
| 同上 | [回答核验接手](2026-10-07-answer-quality-takeover.md) | 同上 |
| 同上 | [D6 修订连续性](2026-10-07-d6-review-continuity.md) | 原质量/真实修订边界保留 |
| 同上 | [Knevo 研究维度](2026-10-07-knevo-market-research-dimensions.md) | #68 的研究维度实施；不等于全面胜过 Pi |

## 第一批已核历史证据

证据根 `~/.finance-runtime/release-1010/`，下列路径在本次写入前已核实存在：

- `main-8b01812bd183/python-receipts/gate-CKo8yPAH/pytest.json`：精确 main，21369P/0F/0E/76S/2X，collected=21447；无收窄，门禁和 full-scope 校验通过。与候选相差的一项 skip 来自锁定 venv 无 tdxpy，不伪装执行通过。
- 同根 `frontend/frontend.json`：六步 exit 0，complete / identity_stable，首尾干净且 revision 相同；registry 五项日志与 doctor 同目录。
- `switch-8b01812bd183/post-switch-validation.json` 及 `post-{health,readiness}.json`：health 版本、干净、加载指纹一致；readiness **12/13**，只有 market_data_consistency 失败，库 10-08、快照 10-09。切换前旧 6c1 同样失败，不将其归因第二批，也不称全就绪。
- `~/.finance-runtime/live-probe-traceability/20261010-post-8b01812bd183-changdian.json`：completed、degrade/secret_scan 为 0，fact_stock_daily 数据日为库内最新 10-08。单题只证链路与该题读数，不认证普遍金融质量。
- 第一批 origin / Gitea main 回读同 8b01812bd。最新备份仍须按 runner manifest 核验，历史成功不担保未来。

## 验收与收尾约束

第二批精确候选 / 合后 main 的新收据存 `~/.finance-runtime/release-1010/wave2/`，结果与准确 SHA 由合集 PR 和该目录运行收据记录。本快照不预先声明尚未完成的门禁、CI、合并或清理成功。

- 本机：锁定 Python 3.12.13 / HTTPX 0.28.1；env -i、umask 022；完整 Ruff / pytest、full-scope 与精确 revision 校验、前端六步、registry 五项。跳过与预期失败单列。
- GitHub：精确 head 所有适用叶子全绿后才正常合并，使用 match-head-commit；不绕分支保护，不把文档保全说成旧草稿代码已验收。
- 合后：准确实际 main 重跑完整门禁；旧 #66/#78/#81/#50 关闭前留下接替或废弃理由。#53 的堆叠状态单独回读，不以 #49 状态推定。
- 清理：仅已获授权且无未提交内容、无进程/启动器引用的树；运行快照与活动 owner 全部保留。清理计划和执行收据留树外，失败不强删。

## 决策与被否方案

| 采用 | 未采用 | 理由 |
| --- | --- | --- |
| 原始 merge 历史 + 追加勘误 | 改写来源提交或静默删错文档 | 保留证据来源，同时阻止旧需求被再次执行 |
| 六份日期文档精确保全 | 整枝合入 #66/#78/#81 | 发布代码已分项接替，旧草稿不能凭文档价值获得代码准入 |
| 第二批不切 8792 | 因 main 新 SHA 就重启线上 | 本批不改问答 runtime，L2 已有独立部署，重启没有对应行为收益 |
| 已存在的 gate / checker / cleanup 入口 | 新建一套发布框架 | 已有工具能覆盖本批身份、收集面和清理边界；不增加第二权威源 |

## 待裁决与保留

- 10-09 行情同步失败、L2 当日失败和外盘日更接线另立数据恢复范围，不能用历史日期调用取最新语义的 daily-full。
- #30/#71/#79、#83 的 D10 范围、正文数值/集合质量唯一负责人及同题对照仍待裁决；#75/#77 在 #83 合入前不关闭。
- 不改其他 Pi 活动树，不代跑原已冻结质量批次，不改公开/私有状态，不发布私有 vidio 溯源分支。
- 保留 6c1 / 8b / bd66 / ffe1 / finance-l2-cleanup、0e3a、trace-* 运行与回滚根。清理前仍以现场引用为准。
