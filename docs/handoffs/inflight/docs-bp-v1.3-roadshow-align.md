# BP v1.5 · 可读性修订 + 申请表同步 · 2026-09-16

## 这个分支做什么
BP 母本/生成版与 product v2 / 口播 v2.3 / PPT v4 同源；纯材料任务。v1.4 交接见 git 历史（f80733b8），v1.3 交接在 `../2026-09-15-bp-v13-before-research-alignment.md`。

## 决策与被否方案
- v1.5 只改可读性与配套件：§2 表去内部编号/术语，事故句改成「上线≠每次任务成功」的例子；否保留 v1.4 原句（评审读不懂 M1–M5 / 质量门）。
- 内容变了就升版号，桌面留 v1.4；否同版号覆盖 PDF（收据绑旧 SHA）。
- 申请表答案重写到研究主干口径；否继续附 v1.2（与 BP 正面冲突）。
- 定价 / 套餐一律不提不改（用户 09-16：不是融资阶段）；Pro 行仍是 offer 草稿原范围。
- foresight 正文与 M-001 分两笔按 hunk 入库；否整文件顺带提交或继续留工作区。

## 当前状态
本树 `docs/bp-v1.3-roadshow-align`：6a90a978 → f80733b8（v1.4）→ 0727ec92（v1.5），工作区干净，未合主线。foresight `feat/advisory-loop`：cc186cf（product v2 / D-008 / 验证补充 / 口播 v2.3 + 归档）、a989f75（M-001）；剩余 specs / advisory 是他人 WIP。桌面：`Foresight-BP-对外版-v1.5-2026-09-16.pdf`（8 页）与 md v1.5；PPT v4 目录已重生成（第 9 页脚注、备注页脚 BP v1.5），旧件归档 `.build/revision-v4.0-2026-09-16-before-slide9-copyedit/`，`.build/delivery-check.json` 重出（pptx 859a5a6a…）。

## 已验证
18 passed（新增：对外版禁内部术语）、build --check、ruff；PDF 回读 8 页 = 8 区块；对外版无 预测 / 涨跌 / 家目录 / 术语；HTML 15 页无越界无报错、演讲者交互过、pptx finalize 过、check-delivery pass（预算整页与 offer 字节不变）。无全仓测试结论。

## 未验证 / 已知边界
未目视 PDF / PPT 版面；PowerPoint 原生字体未验（Arial Unicode MS / Helvetica Neue，Windows 会替换，PDF 为安全件）；未真人计时（口播 1172 字约 5–6 分钟 + 演示 60–90 秒）。桌面申请表 DOCX 与 BP 可编辑 DOCX 仍是 v1.2，本机无 LibreOffice，须按答案文件手工重填。M2 原件脱敏 / 界面彩排未做。

## 下一步
用户目视 v1.5 PDF 与 PPT v4 PDF 并计时；重填申请表 DOCX；合主线需用户确认（合并前跑等价 CI）；合并后删分支与 `fwp-wt-bp-v13`。

## 踩过的坑
`set -e` 下 heredoc python 断言失败没有中止后续 git 命令，扫描要单独跑再提交；BSD sed 不支持 `1,2c\` 多行，patch 头用 python 重写；finalize 拒覆盖，先归档再 rm 最终件 + 收据。
