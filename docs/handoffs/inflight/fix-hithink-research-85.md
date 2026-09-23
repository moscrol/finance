# #85 同花顺研究观察值

## 这个分支做什么
承接#810，前向main，补429有界退避与局部失败，维持日期和生产写入保护。

## 决策与被否方案
- 只将类型化429耗尽转partial；普通错误仍阻断，不能因之前出现过429而重分类。
- 429按monotonic时间与次数双界，4001保旧语义；继续请求不等于允许发布，CLI=3穿透夜跑/单体。
- Quality前轮M1与C2/C3冲突：保留原判，补4项回归，K3独立复审撤销；未为换绿改业务实现。
- 详见 `docs/handoffs/2026-09-24-hithink-research-85-qc.md`；09-23快照保留历史及部署草稿。

## 当前状态
代码候选 `62777a76d7812bf5eebe070892e5977b2aa93003` 已推；WIP PR #894，#810保持打开。编码基线c9dd71dfd，收尾main=5bf47a5ae仅多1个文档合并，漂移校验1≤5、merge-tree干净。
同SHA四叶与K3双轴均已完成。后续文档tip不冒充这张收据的revision。未合/部署/真实采集；未带入主树L2覆盖层。

## 未验证 / 已知边界
- 双轴PASS_WITH_LIMITS：作者测试在审查沙箱收集期blocked；宿主正常94P和全量另账。两组explore提前试跑已披露，只计独立execute一次。
- Quality F2为既存异常分类观察；F3无total空估值的上游可达性未证；F4未知身份拒写符合保护意图。部分读口/恢复路径仅静态核查。
- 未证明真实7至9分钟限流或夜跑恢复；每请求双界，不是整轮时限，也不强制中断在途读取。
- 8792仍是3b7e473575b0，干净且匹配；本候选未装机，数据新鲜度未新验。

## 下一步
1. 等用户确认合并；按最终PR tip补齐门禁，不移签627收据。main再漂移或改代码须重新冻结。
2. #810接替关闭须留指针；当前两张PR均未关，未摘WIP。
3. 部署另授权另立单；installer不会自动把HEAD设为sync根，先核已合SHA快照、plist、生成根和L2身份；本轮不执行部署草稿。

## 已验证
证据根 `~/.finance-runtime/reviews/hithink-research-85-20260923/continue-03/`。
Python14932P/0F/0E/85S/2X，collected15019；Ruff绿。`receipts/gate-ODgFHGso/pytest.json`完整面/身份校验通过，错误SHA拒绝。前端120P、E2E34P/2S；registry五项通过，跨仓已检，98warning单列。
Spec23P、Quality17P均PASS_WITH_LIMITS；故意1F各自单列。429变异2F→2P，错误分类变异3F→恢复4P；原件哈希已验。

## 踩过的坑
STAGE_COMPLETE不等于质量通过；异常可复现不等于违反合同。未用忽略PermissionError的钩子洗绿。复用#75装置，阶段权限仍需其收敛；探针原件已封存，方法进共享知识卡。
