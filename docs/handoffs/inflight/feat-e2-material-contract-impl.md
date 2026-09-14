# feat/e2-material-contract-impl：E2 材料题边界实施（P1v2 退修复审版）

## ⚠️ 撤回（QC R7）
P1v1 交接中「广扫 8039 passed / 4 failed」两张收据归属**错误**：它们来自主检出树
b4a35fa2 脏树（当时命令漏了 cd，收据头部 rev 即为 b4a35fa2），**不能作为 24a79124
的回归证明**，在此撤回。P1v2 的全部验证均在本树（/Users/a77/fwp-wt-e2-impl-p1）
执行，收据 rev 应为新提交号。教训：每个 bash 调用都必须以 cd 开头，本轮已被
cwd 重置咬 9 次（其中一次替换脚本险些改写主树文件，因 marker 不存在而失败幸免）。

## 基线
设计稿 v10 过审（QC b397764f）。P1v1 @ 24a79124 被 QC 退修（4 P1 级 + 3 P2 级），
本提交为退修复审版。

## P1v2 修复映射
- R1 行内第二句漏检 → 句级切分（。！？；\n），每句独立过 _state_op_in_sentence；
  放宽形态（可以查真实数据/结合最新行情）入表。原始 T2 实测：constraint_confirmed，
  premise_declaration + constraint_b 均 message 级。
- R2 引号保护扩张到整行 → 字符级掩码：闭合引号只掩码引用区间（等长空格替换），
  同题行不再被跳过；存储文本按同偏移切回原文，引号内容不丢。
- R3 两处识别条件不一致 → 唯一句级探测器 _state_op_in_sentence，内容复核与指令
  识别共用（「本轮其余条件不变。」顶层识别、引导块/缩进内均落 uncertain）。
- R4 长文无实现 → 邻接规则：疑似指令行与叙述行无空行相连 → adjacent_state_op →
  uncertain（禁令不升级）；题组识别加「题间不得夹正文＋续行须短于
  _MATERIAL_MIN_CHARS」，研报编号小节不再误认成题组。
- R5 强保护被复核重解释 → 内容复核在掩码后文本上做，围栏/引号内禁令不再误报。
- R6 多行题文与题级归属 → 题组吸收紧邻短续行；题内状态操作 scope=q{原编号}
  （题首行检测跳过编号前缀）；message 级假设须强形态（成立/会怎样），题内宽形态。
- R7 广扫收据归属错误 → 见上方撤回。

## 验证（全部本树执行）
- 新测试矩阵 23 passed：真实 T2/T3（从仓内冻结证据 t2-question.txt/t3-question.txt
  加载，非转述）+ 六类退修最小探针 + 回归。
- 定向回归：test_e2_top_level_regions + test_fine_grained_route_length_gate +
  test_user_task = 73 passed + 1 xfailed。
- ruff 干净；字段门禁 ✅ 无新增未读字段。

## 已知残留（交 QC 裁量）
- 研报「问题形态小节标题＋紧随短正文」仍可能被识别为题组（不影响分类——无状态
  操作即 no_constraint_confirmed；只影响 P4 消费 sub_questions 的精度）。
- 单行混合「禁令句＋叙述句」时，叙述部分不进材料区（P4 材料抽取细化时再收）。

## 下一步（P2，待 QC 复审 P1v2 通过后）
TaskFrame 载体（premise_marks 并行字段+默认省略）+ D2 两轴检出 + D3 投影。

## 不要做
- 不在主检出树跑 CI/下结论；不改原始 T3；不跑正式 PK；不宣称材料题契约就绪。
