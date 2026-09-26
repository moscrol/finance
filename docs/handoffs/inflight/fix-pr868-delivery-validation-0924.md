## 这个分支做什么
#910：#868 审查生成器的交付路径校验与沙箱作者测试准入（审查工具，非生产运行时）。#868 已合 main，本 PR 是对 main 的独立 PR，保持 WIP。工作树 `~/fwp-wt-pr910-main-0925`（本地 fix/pr910-main-0925 推到本分支）。09-26 起协调者会话接手，Pi `01a0d35f` 不再推进。

## 决策与被否方案
- 合 main 后 6F：修测试夹具，不改产品。否改封存模板（哈希封存）、否让生成器改写（真批次要新证据根重绑）、否恢复被删的树（治标）。展开 `../2026-09-26-pr910-retired-owner-control.md`。
- 变异用证据目录脚本，不用 run_extraction_mutations.py：它的临时树在 /var/folders，沙箱测试会伪红。

## 当前状态
已前向 main@346be5d8b，代码最后改动 d36a916ef，已推 PR 头。本交接之后无提交。付费请求 0，未合 main、未部署。

## 未验证 / 已知边界
全仓 Python/前端/E2E 本分支未跑（协调者统一四叶）。metadata 放行让受保护子树（.claude/.git/docs 等）可 stat（存在/大小/mtime），正文与列目录仍拒。Keychain 禁令是路径字面量：/usr/bin/security 被拒，拷贝件被 macOS 杀，Security 框架 API 未测。生成器仍默认产出历史 #868 批配置，未跑真批次，无独审结论。C3 端口 26001–26008 多树并发可能耗尽。

## 下一步
协调者四叶后去 WIP 合入。要做 #868 合后独审：新证据根重绑候选/基座/解释器，先真实沙箱预检，再申请额度。

## 踩过的坑
封存输入里的机器路径会随清理失效：路径缺失得到 ENOENT，预检中止，后面的检查一起失效。变异时 basetemp 父目录不存在，0.1 秒 setup error 会冒充红。

## 已验证
定向四目标 200P（13bf6f13e）；终头收据见 PR 评论。6F 在合并前 2da72eef4 同样复现，与 main 无关。复核 PASS_WITH_LIMITS：8 个撤保护变异对照先绿、按预期断言变红、还原干净。记录 `~/.finance-runtime/reviews/unclosed-inventory-20260926/takeover/L1/review.md`。
