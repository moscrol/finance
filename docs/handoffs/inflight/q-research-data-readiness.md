# T3 合流 QC · 2026-09-19

## 这个分支做什么
接续已有T3整合候选，不另开热点实现线。用户授权执行：先保全shim，全部门禁通过才合；红项即停。

## 当前状态
**blocked，未合main/未部署。** 被审业务d12bd0b1，已含基线b22ddf8b；本轮只增加QC探针/证据/交接，不改业务。shim已在Gitea `salvage/opc-shims-20260919@1cc7fb14`按原字节封存，不合该枝。
**P1反例**：`中报原文披露了收入[E1]，但查询返回空白，因此公司没有公告。` 误删可信事实和引用；换句号/分号则保留。真实verifier出口6例4P/2F、exit1（judge off与成功替身均中招）。
详情：`docs/handoffs/2026-09-19-t3-convergence-qc.md`；证据：`docs/verification/2026-09-19-t3-convergence/`。

## 决策与被否方案
- 原字节档案封存shim，否覆盖源码，防把旧备份装成实现；不清原树。
- registry钉三仓版本，否旧KB扫描覆盖新登记；保留首红。
- 行为反例红即停合，否用全量绿替未覆盖行为签字；本轮不代修。

## 未验证 / 已知边界
自然回答仍not_passed，本轮0模型/0新取数；没有真实conversations续修、金融完整性或部署验收。GLM flash/5.3兜底已获较新授权，别沿旧handoff等待GPT Keychain。
比率正文同类误删未出结论；T4/T2公共保稿行为未裁决。8792、夜跑、KB防写均未动，T5/T1等未继续。

## 下一步
1. 在本整合线修错误断言删除粒度，同时保正文/引用；别只换反例标点、放宽条件或xfail。
2. `scripts/review_probes/check_delivery_fact_retention.py --code-root <干净修复树> --expect-revision <完整SHA>` 须从2F转全绿，再验既有反例/同会话续修/最终投影。
3. 新业务SHA重新完整门禁与QC。旧收据不为新提交或main作保；全部通过才按授权合入，部署另办。

## 已验证
已有d12干净Python全量11681P/85S/2x与Ruff0：收据20260919T025205Z-d12bd0b1.json已核身份/依赖/漂移0，非本轮重跑。
本轮定向174P、前端110P与lint/typecheck/build0，E2E34P/2S；固定finance d12/KB1254224be/site f606583三仓registry四项+crosswalk0，前后干净。原宿主registry1因旧rag-query保留不翻写。反例脚本ruff通过、行为exit1。

## 踩过的坑
默认registry扫同级仓；KB旧主树不等于gitea/main。最新174P收据是定向非全量。`_CLAUSE`不切逗号，判错尾部却删整句；私有证据仍在不等于公开正文交付仍在。
