# 8792 引用编号与数量校验隔离：离线修复收据

## 结论与边界

代码提交：`2841ce665b2dae4039ba8c70600c03a48c57fa78`，分支 `fix/citation-numeric-gate-0917`，基于 `gitea/main@0a1cb8c4`。

修复了数字门把正文引用 `E27` 中的 `27` 当作数值阈值的误报；同时挡住证据文字中的引用编号被当成已有数值、进而错误支持正文阈值的反向漏洞。**没有关闭数字门，没有修改公开稿、引用解析语法、契约授权或证据绑定。**

本轮只调用离线确定性代码和测试替身，未调用模型、未修改/重启8792、未部署。未 push、未合 main。本收据不是投资判断正确、整篇研究通过、真实入口修复验收或合并准入证明。

## 实现

- `intelligence/services/episode_protocol.py::strip_evidence_ordinals`：复用现有 `_PROSE_EVIDENCE_REF_RE`，只在分析副本中以空格屏蔽引用编号，不另建引用正则。
- `intelligence/services/episode_semantic_verifier.py`：答案侧 `_novel_numeric_condition_indexes` 和证据侧 `_bound_evidence_quantities` 同用该副本；公开原文仍供表外引用等检查使用。
- `intelligence/tests/test_episode_numeric_citations.py`：31个展开用例，覆盖真实句式、大小写/括号/多引用、真实新阈值、支持值、未知引用、证据编号污染及非引用数字。
- `intelligence/tests/test_episode_protocol.py`：新增6个展开用例，钉住与引用识别共用语法、真实数字保留及重复屏蔽不改变结果。

`PE10`、`1.5E8`、`CE4`、`E0/E027/E1000` 不会获得引用豁免。现有语法没有扩展；日期、单位换算、四舍五入、结构化观察值和推理槽授权仍走原逻辑。

## 冻结生产样本

来源：8792发布版 `bf662e9310ff751a4c31763815ee78fb7d6d5122` 的 hybrid run `run_20260917_203230_060027`。原归档目录：

`~/.local/share/finance-workbench/diagnostics/20260917-sector-history-2030/`

| 数字门输入 | 修复前拒绝句索引 | 修复后拒绝句索引 |
|---|---|---|
| 第20句，原文带 `（E27）` | `[20]` | `[]` |
| 第20句，仅去掉引用 | `[]` | `[]` |
| 原始3个数字拒绝句一起输入 | `[20,24,25]` | `[24,25]` |

**20是句子索引，不是拒绝了20次。** 第20句完整文本保存在 [receipt.json](receipt.json)。同一重放的非引用诊断字段逐项一致：错区间榜、重叠占比、历史错序等没有因本次修复消失。

第24/25句保持原判，只证明未把整个数字门放宽；不代签这两句的全部单位对齐、语义或契约正确性。第20句不再因引用误删，也不等于其金融推断已经获得证据支持。

## 测试与反证

| 检查 | 结果 | 适用范围 |
|---|---|---|
| 修复前新增用例 | 18 failed / 13 passed | 锁住误报及证据侧编号污染 |
| 修复后定向5文件 | 285 passed | 数字门、协议、语义修复、删除权与必需块 |
| 在进程内撤掉编号屏蔽 | 18 failed / 13 passed | 测试能抓修复被撤销；源码未改 |
| 在进程内关闭数字门 | 21 failed / 10 passed | 测试能抓过度放行；源码未改 |
| 还原新进程，定向重跑 | 285 passed | 变异不残留 |
| `ruff check .` | 通过 | 全仓静态检查 |
| 提交后干净树 `pytest -q` | 11,472 passed / 81 skipped / 2 xfailed | `2841ce66`，17 warnings |
| 固定revision收据校验 | 8项通过 | 解释器、依赖、干净树、基座漂移等 |
| 代码提交钩子 | 通过 | 不等于完整registry workflow |

干净全量收据：`~/.finance-runtime/test-receipts/20260917T133812Z-2841ce66.json`，逐字段副本在 [receipt.json](receipt.json)。该数字属于代码提交 `2841ce66`；后续只新增文档，也不改写收据的revision。17个warnings来自市场阶段模型数值计算及旧UTC接口，未在本轮处理。跳过/预期失败不算通过。

**尚未跑**前端四步、浏览器/E2E、完整registry-check workflow、修复版的真实Workbench API/模型会话。因此不能以Python绿灯宣称四叶合并门禁全绿。

## 复现

在本分支工作树运行：

```bash
PY="$HOME/finance-workspace-private/.venv-workbench/bin/python"
"$PY" -m pytest -q \
  intelligence/tests/test_episode_numeric_citations.py \
  intelligence/tests/test_episode_protocol.py \
  intelligence/tests/test_episode_semantic_verifier.py \
  intelligence/tests/test_v8_semantic_deletion_rights.py \
  intelligence/tests/test_ceiling_required_block_degrade.py
```

完整冻结样本重放复用前轮诊断分支的脚本，**不复制第二套量具**：

```bash
REPLAY="$HOME/fwp-wt-8792-sector-history-diag-0917/scripts/replay_sector_history_diagnostic.py"
BUNDLE="$HOME/.local/share/finance-workbench/diagnostics/20260917-sector-history-2030"
"$PY" "$REPLAY" --artifacts-root "$BUNDLE" \
  --runtime-root "$HOME/.finance-runtime/finance-workspace-bf662e9310ff"
"$PY" "$REPLAY" --artifacts-root "$BUNDLE" --runtime-root "$PWD"
```

脚本归属 `docs/8792-sector-history-diag-0917@5a2b45de`；诊断分支收尾提交为 `40321402`。若该树移走，可按提交取回脚本。它的 `runtime_revision` 是**原探针**的健康收据版本，`quantity_tokens` 是原句的裸正则扫描，after中仍显示`27`不表示修复失效；应看 `rejected_with_citation`。脚本exit 0只表示重放完成，不自带修复验收断言。

本轮详细日志、前后重放、三句对照、干净全量原收据已归档到：

`~/.local/share/finance-workbench/diagnostics/20260917-citation-numeric-gate/`

12文件/115,616字节，指纹见 [artifact-manifest.json](artifact-manifest.json)。原件只在本机，未上传；清理磁盘时保留。
