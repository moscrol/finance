# A股研究数据链｜验收结论：不通过（baseline/research-data-acceptance-0922）

## 裁决
候选 `6fb37a6e` **未通过真实回答质量验收**。两题各只首发一次，未重采样。

## 实盘条件（可复现）
代码根＝冻结树 `~/.finance-runtime/convergence-20260919/retention-repair/candidate-6fb37a6e/registry-pinned/finance-workspace-private`，
health 自证 `source_revision=6fb37a6e / source_dirty=false`；写手 **kimi-k3**（本机网关 8080），端口 8907，用户目录在独占根内。
**壳层适配**：候选无条件发 `temperature`，该网关 k3 拒收（sol 接受）→ 首发 HTTP 400、`continuous_runtime_failed`、零产出，作废不计次。
加 `k3_param_shim.py`（8081，仅剥离 `temperature`，不改被测代码）后复发。声明偏差：采样温度变为服务端默认。

## 两题结果
**① historical-iso（历史解禁）＝ 通过原失败形态**
拒绝用当前日程回填，点名东财源是滚动日程且不带披露日；公告通道查询失败被写成「不能据此断言没有相关公告，只能记为证据缺口」；
把「茅台流通盘大、大概率无解禁」明确标为推断而非事实。

**② financial-calc（现金流含金量）＝ 失败**
模型抄错自己的沙箱产物：记录 `2025年报=0.7474`，正文写 `0.7473`——与立项失败形态①（1.588→1.587）同类。
守卫 **findings 为空**。根因用最小对照钉死（`live-calculation-copy-6fb37a6e.json`）：
`_absolute_ratio_label` 不认模型实际产出的列名 `现金流/净利润`，也不认它实际用的措辞 `比值`
→ `_ratio_products` 为空 → 没有任何单元格被对账。只把列名改成 `含金量` 仍不抓；只有夹具形状的句子才抓。
本轮没发出去，**只是因为判官不可用整篇被扣下**（`judge_status=unavailable`），不是守卫起作用。

## 同时复现的两条公告线索（`disclosure-attribution-scope-6fb37a6e.json`，4P/4F，控制 4/4 全过）
未列名场所 `深交所互动易…[E2]` 独立来源句连引用被误删；`因此本期无任何披露文件` 漏检且 status 仍 `completed`。

## 结论口径
交付层三个守卫（公告缺失、归属白名单、比率对账）都是**有限词表**，绑定在模型自选的措辞与列名上。
工程绿（12259P）与 52 组变异全红只证明夹具形状内的行为，**不能外推到真实会话**。

## 下一步（建议）
1. 比率对账改为绑定**计算产物的结构位置**（哪一列是比率由 formulas/schema 声明），不再靠列名词表
2. 公告侧同理：从"关键词匹配"改为"断言类型识别"
3. 判官不可用需单独定位（k3 当判官时 unavailable，写手却正常）
4. 修完重跑本目录两支量具 + 两题实盘，再谈外审

## 红线
未 push / 未开 PR / 未合 main / 未部署；8907、8081 已停，8792 生产全程未动；主树他人改动未碰。
