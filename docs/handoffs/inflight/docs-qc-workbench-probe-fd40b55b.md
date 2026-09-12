# Workbench probe P2 修补复审 · 2026-09-13

## 这个分支做什么
独立质检 fd40b55b + a4befb2e；固定 a294a72e...a4befb2e，仅脚本、测试、交接三文件。

## 决策与被否方案
| 选了 | 否了 | 理由 |
|---|---|---|
| 本机 HTTP + 未改脚本子进程复现 | 只看 mock 测试绿 | 真实失败发生于正文读取和错误处理内部 |
| 两种变异各做前后对照 | 旧取末项绿与新取非空红直接比较 | 错误行为不同，红数不可比 |

## 当前状态
- Standards 0 项；Spec 2 项 P2，均属原 P2-1 未收口。原 P2-2 位置锁关闭。
- 缺口一：脚本149行 HTTPError 内 exc.read() 二次失败不受兄弟 except 保护。
- 缺口二：152/184/207行 OSError 漏 IncompleteRead（它属于 HTTPException）。
- 原交付树 a4befb2e 检查时干净、交接3047字节≤3072。此分支只留质检文档，目标实现未改。
- 详情/复现：`/Users/a77/.finance-runtime/reviews/workbench-probe-fd40b55b-20260913/review.md`，同目录保存脚本与 JSON/变异输出。

## 已验证
- 项目 venv pytest：12 passed；Ruff check/format 通过。
- 干净收据 `~/.finance-runtime/test-receipts/20260912T180443Z-a4befb2e.json`；--expect-revision a4befb2e 校验0。
- 扩展HTTP 21场景：13符合合同；4阶段成功正文截断、创建/提交错误正文超时或截断共8场景均exit1+traceback。
- 同变异前后：last-item 旧7绿→新1红；last-nonempty 旧2红→新3红。变异禁写普通收据，源码未动。

## 未验证 / 已知边界
- 执行方所引175616Z收据是a294a72e且dirty=true，只证明当时工作区；最终提交读数由本轮补齐。
- 未重跑全仓/前端/历史pre-commit。未部署路由或向生产发送T2/T3；exit0不代表答案内容过关。

## 下一步
1. 执行方保护错误正文读取、覆盖HTTP正文截断；补读取边界回归后复验。
2. 用户授权部署后再以新探针取回T2→T3，按题面及run工件检查内容。

## 踩过的坑
- 抓住请求报错不等于错误处理自身不会报错；OSError不覆盖所有网络读取异常。
- 专用复现留在持久评审目录；本轮是审查，未抽通用组件或代改执行方实现。
