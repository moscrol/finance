## 这个分支做什么

接手 PR #61，核对 post59 部署记录，补保留原件的模型身份复核，纠正证据不足的验收表述。

## 决策与被否方案

- 原 run 不改，分别用部署代码和候选代码复核；否补写 trace 或改签旧收据，保留历史身份。
- 缺失 switch/readiness/health 原件明确列为缺件；否拿早一轮 e330 部署产物顶替 d5。
- 合并最新 main 并追加修订；否 rebase 强推，保留原 PR 提交历史。

## 当前状态

修订在 PR #61 接续分支，核对报告及五份原始检查输出已提交。本会话负责剩余核验；未合并、未切换生产。详情见 `docs/verification/2026-10-06-cutover-post59.md`。

## 已验证

`git diff --check` 通过。原 Episode/trace 文件哈希保持不变；部署 d5 检查器两次 exit 2，候选 #66 的 05b776e39 检查器两次 exit 0。精确代码、输入哈希与命令在报告所链 receipt.json，复核采用已有 check_model_admission 工具。

## 未验证 / 已知边界

原部署卸载/恢复时序、readiness、三份 health 原件未留齐，不能补证。模型身份可解析不证明自然投研质量，候选工程修复也未部署。CI 需核对本 PR 当前 head，旧绿灯不移签。

## 下一步

确认当前 head 的 CI 各叶结论后交用户决定合并；以后每次切换保存原始三读及 switch.log。答案与核验修复由 #66 接续。

## 踩过的坑

只检查 continuous-episode.json 会漏掉同目录坏 trace；完整目录才是身份门对象。时间不同、revision 不同的部署产物不能交叉补证。
