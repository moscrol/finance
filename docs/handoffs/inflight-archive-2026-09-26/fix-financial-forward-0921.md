# #835 财务与交付前向整合

## 这个分支做什么
整合#797比例与R6/保稿/发布/研究交付/RAG父实现，保主干新保护。

## 决策与被否方案
financial_claim_mismatch与unknown_stock_code分区共存；否删数字门、关预算就免证据义务，坏差值删掉不清metric补修债。
精确publication与delivery_pending双守；否run终态单独解锁，已提交事件不代表writer结束。测试按真实message.complete→run顺序，不降低产品门迁就旧夹具。
RAG替身隔离RSS观察；否删生产保护/采样任意PID。详见`../2026-09-21-research-tail-forward-integration.md`。

## 当前状态
WIP #835已推d82cb16b5ef31d23339a1bef7084a0dcb8221e15，源码clean；直接基座ea5c3a946（#831），main基座f783f19c8。#797接替评论5369、不关闭。
独立sol审六模块240P后10:41:32Z容量中断exit1，无报告/独立probe，首尾净树；BLOCKED_PROVIDER_CAPACITY，不是运行中、不自动重开。
用户“执行”后本轮只备续接prompt；历史先行又capacity，按串行约定未启动财务。NOT_STARTED_SHARED_PROVIDER_CAPACITY，无新模型调用/测试/report，无待收后台。
交接在docs/research-tail-closeout-0921，不改冻结源码身份。

## 未验证 / 已知边界
旧R6/R3自然0/4仍not_passed，本轮零新自然金融验收；脚本化发布不签真实同会话纠错/答案质量。新组合独立未签，旧#797不可移签。不含main#830/f2c3e9e1，不签三领域联合树；未合/部署/生产操作。

## 下一步
读第三包domain-review-resume-01的not-started/根QC，不等待旧PID；另确认可用订阅与单次额度后补独立消费者反例。历史缺陷不外推财务失败；新main5a5334712或再合流须验实际新树。

## 踩过的坑
RAG替身缺pid、前端发布顺序、测试句号使引文独立分句均有首红，未改产品凑绿。publication六例含after-commit且writer活动窗口；新接缝三例另覆盖股票代码/短日期/引文。
独立首命令/usr/bin/timeout不存在（实际127、外壳0），改Homebrew路径后240P；首输出从events恢复，不称产品错。

## 已验证
固定作者13305P/87S/2X、17W，900.85秒，收据20260921T095428Z-d82cb16b.json；Ruff/四registry/crosswalk0，前端118P、E2E34P2S，六步0、首尾净树。改动树2041P另记不签父HEAD。
封档：`docs/verification/2026-09-21-research-tail-forward/`三包，旧两包不改。
