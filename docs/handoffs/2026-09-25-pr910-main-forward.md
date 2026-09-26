# #910 前向已合入的 #868/main

## 身份与操作

用户本轮原话“执行”，承接最终候选前置工作，不解释为新增付费审查、合 main 或部署授权。owner 评论7092/7095确认 #868 已合入 main，并请本 PR 改指 main。

- 固定基座：`1751e21e0fd30642e0b223604b64b30e38c46f41`。
- 原 #910 HEAD：`2d7b99e6d798269133bce146d36ab46be451ef91`。
- 新代码候选：`4ad2cb42b0c58d9b3997a435568eea5e549bccdb`，两个父提交依次为上述原 HEAD、固定 main。
- 源码树：`7e9b4629af7efb6e45d66b21647a525e512b077f`，与事前 merge-tree 预览完全一致，无冲突、无手工产品改动。
- 自有树：`/Users/a77/fwp-wt-pr910-main-0925`，本地分支 `fix/pr910-main-0925`；发布仍使用原 PR 的 `fix/pr868-delivery-validation-0924`，只允许快进，不强推。
- PR base 已由 `feat/adaptive-research-loop` 改为 `main` 并读回；WIP、open、未合入不变。

相对固定 main 仍只有三份原交接和三份交付/测试文件；#911 的研究链测试不在本候选。后续证据文档提交不自动继承代码候选收据。

## 验证

固定解释器 `/Users/a77/fwp-wt-pi-research/.venv-workbench/bin/python`，Python3.12.13/httpx0.28.1，依赖指纹 `66726d345bf37ce5`。受测前后本树干净。

- workspace doctor、全仓 Ruff、相对 main 的完整 PR diff-check：exit0。
- 注册表 parse/check/tables/views 及台账 crosswalk：五项 exit0。
- 仅四个不争用固定端口的测试：结构化交付绑定拒收、规范探针路径验证、保全封存输入/拒绝复用、篡改归档拒收，**4 passed / 0 failed / 0 error / 0 skipped**。
- `check_test_receipt.py` 对本树唯一收据检查精确 revision、目标、固定 main 零基座漂移：exit0。没有传 `--require-full-scope`，因为这明确是四目标收据。

原始证据根 `~/.finance-runtime/reviews/pr910-911-forward-20260925/910/`。仓内 `docs/verification/2026-09-25-pr910-main-forward/manifest.json` 列27份原件，日志保留原字节，Python执行脚本只封存为txt。临时pytest夹具未放Git。

## 取舍与边界

| 选择 / 否掉 | 原因 |
| --- | --- |
| 原分支前向合并main / 重写历史 | 保留已审过的提交来源，允许非强推快进更新原PR。 |
| 独立候选分账 / 复用fb41整包收据 | 旧组合含#911，且main基座已变；数字不能移签。 |
| 低成本定向检查 / 叠加全量 | 三套他人全量在执行，资源观察拒绝新的全量准入；只跑无固定端口冲突的四项。 |
| 保持WIP / 把4P视为可合 | 真实CLI沙箱、嵌套C3/C7及整个73例修补套件均未在新候选重跑，四叶更未完成。 |

本轮没有重新执行沙箱作者准入/真实工具菜单/预算纠错全链、全仓Python、前端或E2E；没有独立spec/quality、L6、真实金融质量或8792验收。`resource_observation`记录共享宿主当时三套pytest，是观察不是全机锁；不据此归因任何历史红。

旧 `pr910-911-qc-20260925-01` 仍已撤销、不得恢复。当前付费授权0、模型请求0；不借旧余额。没有向#868 owner分支或main推送。

## 下一步

资源允许后，对冻结的新代码候选补完整沙箱作者套件和四叶门禁；若main继续前进，先重评差分并重新绑定候选。工程条件齐备后，明确申请对应候选/范围/预算的独立审查授权，另建新证据根。合 main 和部署必须另外确认。
