# fix/e2-boundary-closeout

## 这个分支做什么
按v10分片收口E2材料边界；只动fwp-wt-e2-boundary-closeout，主树不动。

## 当前状态
用户纠正：独立审查本来可关闭，本轮关闭，不再作为后续工作的前置（纠正04834c55d72b）。撤销93ad74a8的“先等服务恢复”要求；不是独立通过。
应用a819ecde、作者复验0b18f185未变。前三次独立审查均服务中断，无报告；原件保留为历史，不再重试。
第二次af50a26c；第三次7f2f48ca：`docs/verification/e2-boundary-closeout/p3f1-a819ecde-independent-qc3-blocked/`。未推送/合并/部署，不跑正式T2→T3/Knevo。

## 决策与被否方案
- 真实completed用户Message、内容材料ID及message_id绑定；否决正文角色/标题猜来源。
- 共用既有窗口，只取完整消息；summary-only不可恢复，已知空投影不回读prompt。否决无限历史/片段冒充原件。
- 只对当前明确material_only接默认controller及legacy frame重建；旧注入签名兼容，不扩普通/full/local_only。
- 坐标≠事实证据≠权限；不保存正文、不改controller历史提示词。理由见`docs/handoffs/2026-09-15-e2-p3f1-source-binding.md`。
- P3f清空历史已反证撤回，不恢复。可选审查关闭≠通过；否决擅自升级为硬门槛，作者测试及合并/部署授权要求不变。

## 已验证
a819ecde作者干净树八文件249P/禁止尝试0，检查器15P、Ruff通过；三处撤线6F/27P、2F/31P、2F/31P，恢复33P，均0禁止。初版4F/4P与最终八针基线6F/2P不混读。
协调者验Git归档：6f7eef14首次中断9/9、作者复验16/16；af50a26c第二次13/13、7f2f48ca第三次11/11完整。第二/三次审查树固定a819ecde、干净；应用/脚本/测试未改，无新增应用测试读数。

## 未验证 / 已知边界
仍无P3f1独立裁定。相邻两文件110P但100次禁止尝试、shell exit3（83版本子进程/16用户目录扫描/1localhost:3456解析），无审计110P不能洗掉失败。
未盖controller模型历史、pending恢复/已有注入frame重验、D7权限继承、Episode历史正文交付及最终答案；余P3静态路由/日历/未知基底/旁路、local_only更多runner与原题号槽、P4–P7及全仓/前端/E2E合入门禁未完。

## 下一步
1. 直接冻结controller历史提示词及Episode正文送达的下一小片，按真实入口补离线反例并实现；不再启动独立审查者或等服务恢复。
2. 作者验证仍须真实测试、计数、保留失败；来源绑定不能外推全链安全，合并/部署仍待用户确认。
3. harness-reference KIT检查器索引仍待安全专树补登，不动他人BUILD脏改。

## 踩过的坑
shell显式cd；pytest/ruff用主树venv。重叠集合不相加；异常前计数，Python audit非OS沙箱。原件逐字节归档、提交后验Git完整性。CLI exit0与无工具都不能推导测试通过/0禁止尝试。
