# 8792 三类边界返修

## 这个分支做什么
修明确拒登记仍写入、未来复查计划被日期门误删、排版改变财务研究路由；正式回归纳入 pytest。

## 决策与被否方案
- 小句词元扫描替代8字GAP；不关写口、不特判原句，避免无限正则回溯。
- 日期门只判明确来源/发布日期与唯一source_date矛盾；不以日期共现删计划，也不靠无关同日背书。
- 按区域起点分请求/文档；不用长度/编号判材料，报告内部指令不升级。
- 背景、被否方案与收据：`docs/handoffs/2026-09-17-8792-readiness-boundary-fixes.md`。

## 当前状态
树`~/fwp-wt-8792-readiness-fixes`；基线`gitea/main@0a1cb8c4`；代码提交`6f9df75a`，后续仅交接/证据文档。未push/PR/合main/部署，未改开关、真人台账或行情库。8792仍`bf662e9310ff` healthy；两个判官开关未翻。原审查/清盘另枝不混入。

## 未验证 / 已知边界
- 无修复版真实模型Workbench任务；E2E是隔离fixture/用户/测试库，不证明金融答案效果。
- 「若到2026-10-21需求仍未改善，应重新评估 E1。」本枝仍可能被数值门误删；只测试日期函数，未伪造全链通过。相邻`fix/citation-numeric-gate-0917@2841ce66`另修，未组合验证。
- 本单不签#770跨轮材料/local_only，不启用off，不补行情，不签RE06/#53真人效果。中文匹配是保守机械规则，不是完备语义解析。

## 下一步
1. 独立复核固定提交，必要时显式push本分支；合main/部署另等用户确认。
2. 与最新main/数值门/#770整合后重验最终revision，旧收据不迁移。
3. 获授权后隔离真入口覆盖拒登记/计划/排版，冻结模式、模型与数据截止日。

## 踩过的坑
- 共享最近收据会被其他测试覆盖，用下面固定文件，不读SessionStart最近条目代签。
- registry首跑末步脚本名误写，原exit2保留；重跑真实gen_runtime_catalog及五项registry全过。
- 前端离线缺tarball，按锁文件在线安装后全过；端口8793/8795及RE06_E2E_URL同步，服务已停。
- 记忆索引/图谱自动同步2524bcdf；图谱校验过，vault整体19errors前后相同（两文件父版读取对照），不称记忆库全绿。

## 已验证
干净代码`6f9df75a`：11519P/0F/81S/2x，Ruff通过；前端107P、lint/typecheck/build通过；E2E34P/2S；registry五项+catalog通过。收据`~/.finance-runtime/test-receipts/20260917T134635Z-6f9df75a.json`固定revision八项通过。
新增84例在旧版68F/16P、修后全绿；选集892P/4S；原QC15/15；三类撤保护变异见红。原件`~/.finance-runtime/reviews/8792-readiness-fixes-20260917/`；索引`docs/verification/2026-09-17-8792-readiness-fixes/`。文档新头未重跑全量。
