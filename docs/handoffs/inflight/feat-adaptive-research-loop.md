# feat/adaptive-research-loop 在途

## 这个分支做什么

修研究回路取证、窗口收益计算、修订与公开保真；最近真实自然验收内容失败，但本轮已落计算与提示边界修复。

## 决策与被否方案

local_only 四只读能力、根 T900/单发帽75/核验共享窗150 不变，不开 derived_calculation，不重跑旧真实题刷成功。
`finance_query` 受限提供已观测日逐日复利摘要；不用自由文本算术解析器，也不把 `river_query` 个股首前收盘口径冒充板块日涨幅口径。
收益比较必须同窗同实际日期集合、收益差用百分点；空集/gap/失败仍不升级为否定事实。判官不可用仍 partial，但公开提示不再把结构绑定说成计算正确。
完整背景见 `docs/handoffs/2026-09-22-adaptive-return-summary.md`；自然失败见 `docs/handoffs/2026-09-22-adaptive-absence-live.md`。

## 当前状态

收益摘要修复与判官公开提示已完成。新增本地超时诊断探针和定向测试，尚未修改生产传输层；未 push/PR/合 main/部署/fetch，未操作生产8792。完整发现见 `docs/handoffs/2026-09-22-adaptive-timeout-diagnosis.md`。

## 已验证

收益修复准确 SHA 回归 `984 passed, 8 skipped`，变异套件11条逐条撤保护通过。超时探针代码提交 `6f084297b`，定向测试 `14 passed`；本机诊断确认共享窗第三槽零秒拒发有效、根期限耗尽不发请求，但在途 HTTP/流读取会越过 `timeout_asked`。准确收据 `/Users/a77/.finance-runtime/adaptive-timeout-diagnosis-20260922/transport-6f084297b.json`。

## 未验证 / 已知边界

尚未证明旧真实 GLM 请求是响应头停顿、响应体停顿还是持续流式；未修复绝对墙钟截止，也未重跑真实模型。自然模型是否主动用收益摘要、内容方向是否正确、完整 Python/前端/E2E/registry/独立 Spec/Quality 仍未验。

## 下一步

下一阶段修传输层绝对截止与迟到报告拒收，再用 `--assert-deadline` 验收（当前13场景中7个越窗，仍红）。修复前后分记墙钟、请求次数和台账耗时；通过后另预注册真实样本，不重跑旧失败题刷绿；合入前补完整门禁。

## 踩过的坑

pytest 必须用主树 `.venv-workbench/bin/python` 并先建独占 basetemp；提交前回归不能移签提交后 SHA。`timeout_asked` 不是实际耗时，核验轮数、实际调用数、零秒拒发要分账。
