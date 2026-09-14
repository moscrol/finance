# RE06 合并候选审查

## 这个分支做什么
只审 `0bd11ece` 对 `1fef3d27`；原候选树不改。本分支保存报告与反例，代码与候选一致。

## 决策与被否方案
- 暂不放行合并：Y1/Y2 两项 P1 仍复现；I11/I14 两项 P2 工程缺口。
- 工程上支持 Q2 人工确认过渡；不代用户接受。当前所有成功复核均需显式成果确认。
- 不以 10211 全绿覆盖新增反例；两轴细节见 `docs/verification/re06-0bd11ece/REVIEW.md`。

## 当前状态
审查产物在本分支提交；原候选与06交付分支未改，未push、未合main、未部署。

## 已验证
- 候选父节点为 `7abaa938` + `1fef3d27`，归属链代码与第八轮被审代码相同。
- 原X1/X2 + rework/API + Y1/Y2：81 passed / 2 failed。失败：源消息落盘前取消、来源reader故障，均把B从requested/1错改open/2。
- I11新探针1 failed：grant/withdraw logging均accepted，之后研究completed仍写3类测量。
- 正式收据：`~/.finance-runtime/test-receipts/20260914T074137Z-0bd11ece.json`、`20260914T074727Z-0bd11ece.json`。
- 执行方全仓10211P收据真实绑定候选干净树；本轮未重复全仓/前端/E2E。

## 未验证 / 已知边界
- I14无visibilitychange计时接线及浏览器验收，需工程补齐或用户明确缩范围。
- I13/I15真人/前向证据仍pending，不列新增实现bug。
- 自用测量不进真人试点，不能据此豁免I11关闭测量合同。

## 下一步
执行方区分来源absent/pending/error，未知不迁维护状态；补测量启停与I14，再原样重放本目录三针和历史回归。Q2及合并/部署分别由用户裁决。

## 踩过的坑
外部测试文件会让收据hook绑定其所在树。首跑d51b5e6c收据不用作候选凭据；复制原探针后已按候选重跑。收据dirty=false只指代码前缀，worktree_dirty_total仍记录审查新增文件。
本轮复用已有反例手法，无新通用工具；未为审查改应用门禁或重写共享harness。
