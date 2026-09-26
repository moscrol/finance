# PR #868 审查工装修复

状态：**OFFLINE_PROTOCOL_VERIFIED**。代码提交 `324a76f9a75fde1a25e979e5ade26e63a8dfaf30`；本次仅修工装，不改产品源码、生产配置或旧证据。

## 修复内容

- `scripts/review_probes/prepare_pi_review_repair.py` 从已封存的 1830 批输入生成新目录。先校验 44 份输入哈希，拒绝覆盖已有目录或写入封存根；不继承运行收据、模型输出和授权。历史作者输入原样保留，不给旧测试移签。
- 三阶段的实际 pi `--tools` 名单均包含 `deliver_stage`，按阶段收窄；启动时将实际工具集与配置比较，遗漏即在请求前退出。提交工具必须单独出现，不能和其他工具同轮提交。
- `pi_review_protocol.mjs` 强制 `read -> write -> final` 跨响应状态机。只有成功读取返回后才开放 write；只接受读取到的精确内容，成功落盘后才开放纯文本终稿。错误路径、读取失败、同轮多工具、猜测副本或提前终稿均拒绝。
- 网关检查先于请求记账。被状态机拒绝的后续尝试留阻塞原因，不误记为已外发请求。控制器还必须看到 `gateway-state.json` 的 `complete`，不会仅凭 exit 0 或正确回显判绿。

## 验证

固定 Python：`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`；实际 pi CLI：`0.85.1`。

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  tests/test_pi_review_repair.py tests/test_k3_review_shim.py tests/test_adaptive_l6_audit.py
```

固定代码提交、干净工作树：**55 passed / 0 failed / 0 errors / 0 skipped**。其中新增工装测试 25 项。Ruff、Node 语法、提交钩子通过。

- `pytest-receipt.json` 是上述固定提交的原始收据；`check_test_receipt.py --expect-revision 324a76f9a` 在该提交上 exit 0。它是三个文件的定向测试，不是全仓门禁，也不自动归属后续文档提交。
- 新测试实际启动 pi，并让脚本化回环 HTTP 假服务返回响应。23 份假服务收据共 **27 次本地请求 / 0 次真实模型请求**，含 5 个零请求场景；不是 GLM 服务端兼容性或内容质量证明。
- Gateway 和三个正式阶段均有真实 CLI 零请求启动检查。恢复旧 CLI 名单会在请求前失败；Spec/Quality 三阶段可实际调用提交工具并终止，不再发后续模型请求。
- 网关正例三轮完成；同轮读写、先写、错副本、提前终稿、错终稿、读取报错、错路径、错范围均有反例。控制器正例和拒绝反例的收据计数与假服务接收数一致。
- 新输入根 Spec/Quality 原有沙箱检查均 PASS，真实模型请求 0；验证只准回环 26001-26008、拒绝工具访问网关/8792、越界读写/凭证读取/软链写逃逸及失败退出保真。这是工装测试，不是作者测试或产品审查探针。
- 旧批次 167 份归档及对应私有原件重新核验，差异 0；新生成 42 份输入哈希差异 0。候选树保持干净，19899 已释放。

## 证据边界

私有根：`~/.finance-runtime/reviews/pr868-pi-protocol-repair-20260923-1900/`。

- `inputs/` 是实际生成的新输入，状态 `PREPARED_NOT_AUTHORIZED`；其中只有离线沙箱结果，没有真实 gateway 或正式阶段收据。
- `offline-tests-03-clean/` 和 `pytest-03-clean.xml` 是最终固定提交测试原件。测试中的 `PASS` / `STAGE_COMPLETE` 均为**合成夹具**，不能用于真实审查准入。凭据助手在测试目录中替换成固定假字符串，不读取 Keychain。
- 保留开发过程失败：计数反例为 24P/1F，修正钩子顺序后通过；首次指定持久化 pytest 目录时父目录不存在，16P/39 个 setup error，随后修正运行目录。两份失败收据随包保留，不改写成通过。
- 未运行真实 GLM/K3、作者测试、产品独审探针、自然金融题或全仓工程门禁。未合入、未部署、未推送。#75 仍缺独立 Spec/Quality 终稿，#76 L6 仍 `NOT_PASSED`、实际 `1/1/0`。

## 后续使用

新一轮真实审查必须先重新授权、冻结候选/base、另建证据根；不得复用本次测试目录的合成收据。

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  scripts/review_probes/prepare_pi_review_repair.py <全新不存在的目录>
```

该命令只生成输入，不请求模型。它是针对当前封存版本的可核验迁移，不是通用生产审查器；归档输入或迁移锚点变化时拒绝执行。生成成功不代替新的沙箱/网关准入，也不授权启动 runner。

决策与交接见 `docs/handoffs/2026-09-23-pi-review-protocol-repair.md`。
