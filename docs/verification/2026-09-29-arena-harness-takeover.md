> 历史检查点，当前状态已由[本轮收口](2026-09-29-arena-harness-final.md)替代：访问恢复，四次原始记录已齐，v2候选未过并已在接续分支撤回。

# 8792 harness 接手执行记录

**状态：已接手并完成本轮离线验证；真实回答验收尚未执行，未发布。**

## 已完成

| 项目 | 本轮结果 |
|---|---|
| 隔离接续 | 从原试验提交 `f37629829` 建立 `fix/8792-harness-takeover-0929`，不覆盖原 review worktree |
| 新增代码 | 仅新增一份测试文件、16 项边界测试；没有修改试验运行时代码 |
| 测试提交 | `dfd8d564f7ac349c93908c03d667959716d1b0b1` |
| 固定提交复测 | 35 个文件：**1061 passed / 4 skipped，22.06 秒**；测试前后工作树干净 |
| 静态检查 | 本轮目标文件 Ruff 通过；正常提交 hooks 通过，未跳过门禁 |
| 原题恢复 | news、transmission 各找到四份归档记录，同题四份的题面哈希分别完全一致 |
| 生产保护 | 未合 main、未部署、未重启 8792/8798、未写行情数据库、未发模型请求 |

新增测试验证了：原文标点、Markdown、跨语言文本及 Unicode 字节不被改写；正文中的伪编号不是目录；片段别名按当前冻结合同解析；取消、截止时间、反复坏稿不解除预算约束；v2 作者开关不破坏旧格式读取。

**这些结果只证明相关机械边界通过离线测试，不证明消息八问已可用，也不证明财务推理正确。** 本轮不是全仓门禁；没有用此前别的提交的全仓读数充当本轮验收。

四项跳过分别为：两项缺少 Codex desktop binary、一项真实 headless smoke 未显式启用、一项 deadline 分窗不适用于脚本回放桩。没有将跳过项算作通过。

## 尚未开始的真实对照

沿用原计划，不改题、不增加重试、不挑稿：

1. OFF-news
2. ON-news
3. ON-transmission
4. OFF-transmission

每次独立新会话、隔离用户和 Episode 存储，同一代码提交；保持原部署的模型选择、预算和判官配置。候选 news 必须八问可用且零 quote 失配，财务不得新增重大错误；旧财务错误仍应判 partial。候选失败则撤去运行时代码试验，保留全部记录。两个题目不能证明稳定性或能力追平。

### 当前前置条件

- **原预算数值及部署配置尚未完成核实。** 仓内对照汇总只给出了 controls 相同的布尔结果，不能替代原始预算收据；相关原件与生产 launcher 位于当前 MCP 项目文件范围外。本轮未通过任意命令绕读。
- **独立审查尚未完成。** 本助手的代码阅读与新增测试不是另一份独立审查结果；仍需可执行的独立代码/内容审查入口。
- **模型连接尚未核实。** 对旧验收脚本文档所列 `127.0.0.1:57244/v1/models` 的只读预检连接失败。这不证明当前生产模型不可用——其实际配置端点尚未确认。8792 `/api/health` 为 200，仍报告运行 `62fad1d0d986`；health 的默认 `glm-5.3-flash` 不能冒充这两题应使用的实际模型。归档评估报告记载两题使用 `glm-5.3`，后续必须核对新的 `served_model`。

因此本轮没有消耗四次首发机会，也没有用默认配置或新模型凑一组不可比结果。

## 位置与证据

Mac 接续树：

```text
/Users/a77/finance-workspace-private/.worktrees/arena-8792-harness-takeover-0929
```

新增测试：`intelligence/tests/test_material_source_excerpt_boundaries.py`。

原题 SHA-256：

```text
news         e9fc5dae9b0b816a4993b21c1d961242126e563aaf25fa5ae000a0419d1f0da5
transmission 4f733f678981da95f2414473b7ee3fd42db94e5aa03a32d32f0696fa7812dd18
```

Mac pytest 输出登记的收据：`~/.finance-runtime/test-receipts/20260929T092112Z-dfd8d564-30411dbf014b.json`。本轮保存了执行命令、输出与前后 Git 身份；未越界读取该树外收据文件。

仓内 `docs/verification/material-source-excerpts-takeover-2026-09-29/`：
- `frozen-regression.json`：固定提交上的实际命令、测试输出、跳过原因、Ruff 与前后 Git 状态。
- `regression-targets.json`：35 个定向测试文件，明确测试范围。
- `checkpoint-commit.json`：正常提交与 hooks 结果。
- `cases.json`：原题、哈希、出处与原评审规则；实际作者请求只可取 question，不可混入评审规则或旧答。
- `preflight.json`、`official-api-preflight.json`：待办条件和只读连接预检。

**下一步需要开放合规的隔离验收/独立审查入口，或让相关配置与原预算记录在当前 Bridge 授权范围内可用；不需要在聊天中提供密钥。完成这些前置条件后，才冻结正式试验提交并执行四次对照。**
