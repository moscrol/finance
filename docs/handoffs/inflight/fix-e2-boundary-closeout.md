# fix/e2-boundary-closeout

## 这个分支做什么
按v10分片收口E2材料边界；只动fwp-wt-e2-boundary-closeout，主树不动。

## 当前状态
`a819ecde` 已提交P3f1真实消息材料身份绑定及作者归档；固定干净检出复验完成。待独立QC，不推进正式T2→T3/Knevo，未推送/合并/部署。
P3e独立通过仅限词典闸门；原P3f一律清空历史已反证撤回，不恢复该方案。

## 决策与被否方案
- 从completed用户Message、内容材料ID及message_id绑定；否决从正文角色/标题猜来源，防伪装和误截断。
- 共用既有窗口，只取完整消息；否决无限历史/片段冒充原件。summary-only标不可恢复，已知空投影不回读prompt。
- 当前明确material_only才启用；默认controller及legacy frame重建接线，旧注入签名兼容，不扩大到普通/full/local_only。
- 坐标≠事实证据≠权限；本片不保存正文、不改controller历史提示词。完整理由：`docs/handoffs/2026-09-15-e2-p3f1-source-binding.md`。

## 已验证
a819ecde干净树作者八文件249P/禁止尝试0，检查器15P、Ruff通过。三处撤线6F/27P、2F/31P、2F/31P，恢复33P，均0禁止尝试。初版4F/4P；最终八针加来源坐标后基线6F/2P，不混读。
Git归档P3f1 68/68、P3e 26/26、被否P3f 27/27。固定提交收据：`docs/verification/e2-boundary-closeout/p3f1-a819ecde-committed-recheck/`。

## 未验证 / 已知边界
P3f1无独立QC。相邻两文件110P但100次禁止尝试、shell exit3：83次版本子进程、16次用户目录扫描、1次localhost:3456解析。无审计110P不能洗掉失败；尚无该集合零尝试结论。
未盖controller模型历史、pending恢复/已有注入frame重验、D7权限继承、Episode历史正文交付、最终答案。其余P3静态路由/日历/未知基底/旁路、local_only更多runner与原题号槽、P4–P7及全仓/前端/E2E合入门禁仍未完。

## 下一步
1. 独立上下文复核a819ecde及新正反例，先读作者范围与原失败，不把作者复跑称QC。
2. 通过后再冻结历史提示词及正文送达小片，不能直接宣称来源全链安全。
3. 能力图谱有他人脏改；harness-reference BUILD也脏且HEAD领先远端1，图谱/KIT工具索引待安全专树回写。

## 踩过的坑
shell显式cd；pytest/ruff用主树venv。重叠集合不相加；计数先于异常，Python audit不是OS沙箱。原证据逐字节保留、提交后检查Git blob完整性。初版八针未单独快照，before日志留函数；最终快照不冒充初版。
