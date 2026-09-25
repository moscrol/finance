# feat/pi-research-loop

## 这个分支做什么
兑现8792的Pi式研究行为；#911交付离线机制及进程内API组合，真实质量仍待独审和授权验收。

## 决策与被否方案
复用现有Episode/Harness；否第三条Loop、Shell扩权、替换整个Adapter。共享环境漂移时在本树bootstrap锁定venv，否修改并行owner环境。只交测试、不追入正在独审的新候选。理由/失败史见`../2026-09-25-pi-research-http-offline.md`。

## 当前状态
代码0c57cd0d7181已推现有WIP #911，base=feat/adaptive-research-loop；本轮仅新增test_workbench_research_chain.py，无生产差分。底层仍组合f2610293f，不代表#868新HEAD89624eac7e76。#910路径修补仍独立交付，未替owner采用或合main。
新20场景走真实路由/调度/Adapter/Runtime/Harness/持久化，模型及源替身；开关双态、观察追查、空/错恢复、伪造拒收、身份和稿件一致性、两类变异。不是自然质量。
09-25约00:51重读next批授权已approved=true，candidate=f261、baseline=03352758c，本批78/累计291；spec网关4请求预检PASS，非QC。STATE尚写未授权，已滞后。该批归原owner，本会话真实模型0，不动其输入/预算；下次必须重核。

## 未验证 / 已知边界
TestClient为进程内ASGI，不是TCP、浏览器或8792活进程。判官脚本化通过，不验自然语义/修稿/反证；真实源/子研究未验。未跑完整四叶门禁，不移签#868新候选、未来组合或后续文档HEAD。
本树独立.venv-workbench已按锁安装，doctor=ready/无依赖漂移；共享venv未改。代码地图在新提交后需刷新，不作当前架构完整性声明。

## 下一步
1. owner在当前冻结独审批次之外审阅采用#910/#911；最终组合重验，不借旧收据。
2. 重核next批授权和结果，不能沿用旧2105余量，也不能把预检当独审闭合。
3. 独审后按#76/L6逐行自然验收；合main、8792部署分别确认。

## 踩过的坑
消息终态不证明所有审计工件发布完；只join测试自有执行器，再读工件并撤销替身。空工具返回也须ProviderTrace。负向变异须匹配具体断言，不能任意AssertionError就算抓到。

## 已验证
干净0c57cd0d7181十目标787P/0F/0E/3S/1X，collected791；Ruff/提交钩子通过。3S为参照后端不适用/接口限制，1X既有codex缺resume收据。
收据`~/.finance-runtime/test-receipts/20260924T165102Z-0c57cd0d-bcce35088223.json`已精确SHA+十目标校验。Python3.12.13/httpx0.28.1，指纹66726d345bf37ce5。本结果非全仓门禁；旧606P/57P仍只归其原版本。
