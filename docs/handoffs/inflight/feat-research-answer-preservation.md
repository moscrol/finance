# 研究答案保留｜2026-09-18

## 这个分支做什么
普通质量问题保留同任务安全分析，追加疑点/修订；展示不等于核验通过。

## 决策与被否方案
| 选了 | 否了 | 原因 |
|---|---|---|
| 保正文、诚实partial/rejected | 删句或关检测 | 交付与认证分开 |
| 安全正文先判空，再批注 | 用来源注/占位符撑稿 | 派生说明不是分析 |
| 精确追加、核E号与题段 | 模糊diff/无限补写 | 身份、字数和预算不变 |
详见 `docs/handoffs/2026-09-18-research-answer-preservation.md`。

## 当前状态
代码已提交 `5f3b5b593183aae86a93372149efe6611a92ebc8`，前置引用修复478ca199；本次收尾只改文档。未push/开PR/合main/部署。
**整体保留验收未过**：一次真会话保住979字已准入稿，但更早两稿遭准入拒收后被恢复稿替换。
8848/PID94957已停，自己的live锁已移除；8792仍bf662e9310ff，前后身份一致。证据R=`~/.finance-runtime/reviews/research-answer-preservation-20260918/`，214份已封存，清机保留。

## 已验证
固定干净5f3b5b59：Python11594P/81S/2X；前端107P，E2E34P/2S；Ruff/结构门/registry通过，crosswalk98警告。收据 `~/.finance-runtime/test-receipts/20260918T031822Z-5f3b5b59.json` 校验通过，不移绑文档SHA。
真run `run_20260918_113122_450933`：一次首题、零重采样；原979字→批注1102字→历史notice1145字，API精确消息等于answer.md。数字0.4疑点保留，judge rejected/report partial；限定范围秘密与公开泄漏扫描零命中。

## 未验证 / 已知边界
turn-6正文+JSON遭not_json_object；turn-7合法JSON的890字draft遭history_missing_comparison；两者未送达。末端14项绿不能证明全过程保留。
SDK/finish各出口、_carry_repair_finish、旧helper/eval未全审；1200字/12卡/360字符生成上限仍在。旧链真模型、浏览器研究点击、独立QC及金融质量未验。本机Node26/DuckDB1.5.4非CI固定环境；原七类金融问题另线。

## 下一步
从R的continuous-episode.json两次拒收建立确定性红测；分离“候选正文可展示”和“finish/绑定已准入”，保持历史完成度partial及安全硬拒，再做新revision回归。原件路径/完整边界见 `docs/verification/2026-09-18-research-answer-preservation/README.md`。
不要关闭历史比较判据换取通过，不覆盖本次not_passed或自动重采样。

## 踩过的坑
先清洗正文后加说明；同hash还需核语义元数据，旧unknown E不能被新卡复活。准入后成功≠准入前没丢稿；finalization_recovered不是超时结转实测。SessionStart最近收据可能属别树；量具勿命名inspect.py遮蔽标准库。
