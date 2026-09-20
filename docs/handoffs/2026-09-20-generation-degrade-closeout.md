# 2026-09-20 capability-wiring尾提交前向收尾

## 身份

基底gitea/main `728f327160bbd2485cb635e7ef09d040d718d7b5`，新分支fix/generation-degrade-closeout-0920，代码 `c45ad5f853a53b96f7f369c1295027770d20aa5d`，PR #805 open、未合、未部署。

旧fix/capability-wiring-closeout的#732只合到6e1fb1b2，之后6c7bea6e、413b7a07、e8a63007并未因为#732 merged就自动交付。旧树保留、不改，三个补丁已导出到 `~/.finance-runtime/reviews/stale-work-closeout-20260920/source-backup/`。

## 逐项对账

| 旧提交内容 | 当前判断 | 处置 |
|---|---|---|
| 413b7a07生成失败留痕 | main仅在方法论分支记录；知识检索兜底可掩盖生成失败 | 本PR前向窄修复 |
| 6c7bea6e材料正文进证据账本 | 旧实现从聊天文本重建证据，不能直接用于现有冻结材料/来源权限合同 | 交#770确认合同和净增量，不宣称已实现 |
| 6c7bea6e无指代词requests_recompute | main及E2树没有同名谓词，不足以断言所有重算场景缺失；旧真实样本没有今日版本收据 | 待验证“同一批数重算”绑定同一材料/计算输入哈希，不直接放宽权限 |
| 6c7bea6e fincalc.table两参形式 | main和E2仍是三参接口，沙箱prelude仍v2 | 独立剩余项，不能随材料方案一起丢弃；兼容接口与prelude身份另拆 |
| e8a63007交接 | 历史状态与当前合同不同 | 留原件，不整段复制 |

## 修复和反例

新增message/run/report三处一致性断言：生成失败但检索有引用仍须记录生成失败；检索亦失败时保留两条不同警告。正常生成仍无降级；方法论措辞不变。

未修实现2F2P，修后orchestrator/lane两文件107P。固定代码提交扩大到Workbench API、conversation materials及test_e2_*，584P4S。4S均为既有嵌套标签测试。Ruff全仓、提交门禁和精确SHA收据通过，前后HEAD相同、status为空。

没有改变调用次数、预算、重试、检索范围或材料权限。`completed`是回合结束，不保证正文经过正常综述。只覆盖显式fallback_reason，不证明上游空reason或直接抛异常的所有行为。

| 被否方案 | 理由 |
|---|---|
| 原样cherry-pick所有尾提交 | 把不同合同的材料改动捆绑到简单留痕修复，无法独立验收 |
| 兜底有引用就不报降级 | 引用可核验不等于生成成功，运行状态会误导用户 |
| 宣称E2已吸收整个6c7bea6e | 两参表格和重算净增量尚未交付/验证，无证据支持 |
| 复跑旧真实W1和付费判官 | 本轮无该授权，历史收据不应移签新版本 |

## 收据与后续

外部证据根 `~/.finance-runtime/reviews/stale-work-closeout-20260920/`；fixed目录是代码SHA的原始窄回归，不借用旧9219P或#803全量。仓内副本见 `docs/verification/2026-09-20-generation-degrade/`。文档后续tip由PR评论给新复跑身份，不移签。

运行环境env-i、umask022、主树venv；临时用户/episode目录和不存在的测试DB。已有receipt_redirect仅重定向收据输出，首轮red落在共享收据目录，不改历史原件。

下一步审#805、固定最终tip补合并准入并等待用户确认。与#770对账材料身份和重算需求；没有真实模型、自然会话或生产8792验收，也没有全量Python/前端/E2E/跨仓registry/独立外审。旧树仍非删除候选。宽基和其他旧任务状态见#806的日期快照。

工具沉淀：测试/收据/PR全部复用既有工具；一次性runner和日志归档只是本轮证据，不新增通用框架或生产入口。
