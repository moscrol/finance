# 工单 #53 第三轮独立复审

## 这个分支做什么
固定审 b916091e 的两笔修复；原六反例通过，仍有3项P2，不放行合并。

## 当前状态
报告与可执行反例已提交 91d7472e；实现未改，未推/未合/未部署。树 `/tmp/extraction-qc-b916091e`。实现枝读取时顶端642c3f5d，仅较候选新增文档。
报告 `docs/verification/2026-09-14-extraction-b916091e-qc.md`；耐久日志 `~/.finance-runtime/reviews/extraction-b916091e-20260914/`。

## 决策与被否方案
- Q1：确认复用草稿保留请求选定的读取尝试；否了拿草稿提交尝试覆盖它，两者不是同一个身份。
- Q2：已有完成收据先按其source_draft_id选版；否了先取同尝试最新稿，关闭失败后可提交未读新版本。
- Q3：手填显式关联不得向abandoned旧尝试新增确认/checkpoint；不能把旧草稿合法引用扩成所有终态免校验，也不能反过来一刀切禁引用。
完整序列/理由/定位见报告Q1–Q3。

## 已验证
- 独立反例7P/3F：原六项（confirm/skip各测）通过；三残留实测红。
- 10仓内相关模块296P；全仓ruff通过；merge-tree对1fef3d27无冲突。
- 原19变异独立重放：逐个exit1→0，完整traceback落日志；复原116P、变异树干净。
- 提交者b916091e全量9671P/0F收据validator过：revision/依赖/解释器/干净树自洽，不是本轮重跑全量。

## 未验证 / 已知边界
未重跑全仓pytest/前端/端到端/registry，不证明组合树门禁。真实库身份及真人效果未测。SSE首跑红归因只核留档，不独立认定动态零路径交集。
实现inflight仍固定8410e9d3；最新验证页§8复跑命令仍检出7a86ce4e，应修字。

## 下一步
修复者复跑 `scripts/review_probes/check_extraction_attempt_contract.py`，基准7P/3F，修后须10P；保留原19变异与合法旧草稿引用。合入前对最新main重验全部叶子，且等用户明说。

## 踩过的坑
旧规范探针硬插旧worktree到sys.path，不能仅改PYTHONPATH便声称已测新提交。独立探针已落scripts/review_probes供显式pytest，不混进默认套件。首次targeted误写文件名零收集，296P来自修正后完整重跑。
