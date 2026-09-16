# fix/re06-i11-consent-measurement · 研究进化 06 全批次合并候选（含 I11 修复）

## 这个分支做什么
把研究进化六个工作流一次带进 main：06 `3add63d5`（已含 01/02/04/05 尖端）+ I11 同意门修复 + 前向合并 `gitea/main@727b2611` + 03 尖端 `68aac886`。候选 **`50074c76`**。实测与读数全在 `docs/verification/2026-09-16-re06-i11-consent-gate.md`。

## 决策与被否方案
- I11：`ObservingRunStore` 写测量事件前过同意门——owner 表达过同意范围就必须 `research`+`logging` 同时生效，没有任何记录保持自用默认照写。否了「默认不写」（翻转自用语义）与「只看 logging」（与 05 读侧 `REQUIRED_MEASUREMENT_SCOPES` 不一致）。
- Q2 过渡合同按用户委托接受（批次 README §1「维护动作由用户在产品中明确执行」的直接推论；可翻案，改回不迁数据）。
- 03 尖端一起带上：06 联测用的是旧版 f2a12fa3，尖端多 RV1–RV3 返修且目录独占、merge-tree 干净。
- I14 不纳入：`fix/re06-visibility-timing` 叠在 c5359120 上且自述仍开，合并后 rebase 单独验。

## 当前状态
- 候选 `50074c76` 四叶全绿：pytest **10362P / 0F / 77S / 2xf**（收据 `20260916T031253Z-50074c76.json`，`check_test_receipt --expect-revision` exit 0）、前端四步 0（94 tests）、e2e 31P/2sk、注册表五步 0、ruff 0；复核方 3–8 轮 + 合并复核探针 27/27（收据 `20260916T030137Z-50074c76.json`）。
- 第九轮独立复核进行中（分支 `docs/qc-re06-i11-50074c76`）。**合并等它放行 + 用户已委托的授权**；PR 见 Gitea（本文写成时刚开）。
- main 已前进到 `8bb20aa9`（#749 全是 docs/knevo，零交集）。

## 已验证
见 verification 文档 §3–§4；I11 原探针在 `3add63d5` 红、在候选绿，其余 23 条探针修前修后都绿。

## 未验证 / 已知边界
- 第九轮复核结论；I13/I15 真人 / 前向证据（授权后才有）；I14。
- 8792 未切；生产用户态无 consent 记录 → 行为与合并前相同（自用默认）。

## 下一步
1. 第九轮放行 → API 合并（`Do: merge`，删分支）→ 核 `git diff 50074c76 gitea/main` 只剩 #749 的 docs。
2. 合并后：`fix/re06-visibility-timing` rebase；RE 六份 spec 所在 `docs/river-next-specs` 仍未合，需另开 PR 把 spec 入库。
3. 8792 切流是用户决定；切前 `kill -9` 演练与 #23 的 ≥20 真实 run 读数一并补。

## 踩过的坑
- zsh 不分词：`for c in "backfill-tables --check"; build_registry.py $c` 把整串喂给 argparse → 假红（`invalid choice`）；干净 main 复跑同命令才发现是自己的 shell。
- 复核探针多份同名 `test_review_round8.py` 在 `docs/verification/*/`（无 `__init__.py`）一起收集会撞模块名，收编时改 basename。
- 预览树里别人的分支会动：BP 分支在我门禁跑的 20 分钟里被作者推进两次，已从批次剔除。
