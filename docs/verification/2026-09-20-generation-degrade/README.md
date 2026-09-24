# 生成降级收尾作者证据

PR #805，代码SHA c45ad5f853a53b96f7f369c1295027770d20aa5d，基底728f327160bbd2485cb635e7ef09d040d718d7b5。

- `pytest-red.txt`：未修实现2F2P，选择器 `static_knowledge or methodology_lane`。
- `pytest-fixed.txt` / `receipt-fixed.json`：固定代码SHA 584P4S；orchestrator、lane generation、conversation materials、Workbench API及test_e2_*。四条skip为既有嵌套标签用例。
- `head-*.txt`与`status-*.txt`：测试前后SHA同、树干净；`receipt-check-fixed.txt`严格匹配通过；`ruff-fixed.txt`全仓静态检查通过。
- `run-focused.sh.txt`与`receipt_redirect.py.txt`是一次性验证原样留档，后者仅重定向收据。早先red未使用该插件。
- `SHA256SUMS`覆盖以上12个证据文件，可用 `shasum -a 256 -c SHA256SUMS` 校验。不要改写已绑定哈希的原日志。

旧capability三补丁保存在外部证据根source-backup，原Git分支仍保留：

| 原件 | SHA-256 |
|---|---|
| 0001-feat-material-evidence.patch | 00c1a526afbe87cfa0fc6d54c729c7d8be4eb4da33015fe37807261026500757 |
| 0002-fix-degrade.patch | 2eeb7b1c736a01801922459745a81f5f9ea60a2fd958352342df754e0153708a |
| 0003-docs-handoff-06.patch | add98f4371289b871623584ba58342611fc7b65f73c6b353a1c9e4a6d2512b75 |

仅作者窄回归，不签全量CI、独立审查、真实会话、材料/重算或生产部署。文档后续tip不能继承这里代码SHA收据，最终复跑另见PR评论。
