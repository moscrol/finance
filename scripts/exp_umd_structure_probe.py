"""三臂深挖答案的结构覆盖探针：注入的方法论卡有没有改变输出结构。

盲评分捕捉整体质量；本探针直接数「卡片要求的结构要素」在各臂答案里的出现，
回答更机械的问题：注入 2066 字方法论后，答案是否长出了卡片要求的骨架。
关键词组来自附带库 13 张卡的 applies_to 与 prompt_rule 高频要素。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

STRUCTURE_ELEMENTS: dict[str, list[str]] = {
    "生命周期判断": ["生命周期", "旧逻辑唤醒", "升温验证", "高位分歧", "加速定价", "证伪退出"],
    "市场结构推演": ["市场结构", "大盘阶段", "MA5", "情绪阶段", "市场风格"],
    "板块/题材结构": ["双红", "涨停热度", "容量", "主线", "补涨", "高低切"],
    "证据硬度分层": ["证据硬度", "L1", "L3", "公告", "互动易", "订单", "客户验证"],
    "产业链与二阶导": ["产业链", "二阶导", "上游", "下游", "替代", "暴露"],
    "反证与证伪": ["反证", "证伪", "失效", "风险", "反方"],
    "个股身份": ["相对强度", "启动核心", "趋势延续", "分歧承接", "兑现", "身份"],
    "收入/财务传导": ["收入结构", "毛利率", "财务传导", "弹性", "基本盘", "第二曲线"],
}


def coverage(answer: str) -> dict[str, int]:
    return {
        group: sum(1 for kw in kws if kw in answer) for group, kws in STRUCTURE_ELEMENTS.items()
    }


def main() -> int:
    path = Path(sys.argv[1])
    payload = json.loads(path.read_text(encoding="utf-8"))
    by_case: dict[str, dict[str, dict]] = {}
    for r in payload["answers"]:
        by_case.setdefault(str(r["case_id"]), {})[str(r["arm"])] = r

    arms = ["coldstart", "shared_pack", "veteran"]
    for cid, arm_rows in by_case.items():
        print(f"\n== {cid}")
        print(f"{'结构要素':14s}" + "".join(f"{a:>12s}" for a in arms) + "   命中词示例")
        covs = {a: coverage(str(arm_rows[a].get("answer", ""))) for a in arms if a in arm_rows}
        for group, kws in STRUCTURE_ELEMENTS.items():
            row = f"{group:14s}"
            for a in arms:
                row += f"{covs.get(a, {}).get(group, 0):>12d}"
            hits = [
                kw
                for kw in kws
                if any(kw in str(arm_rows[a].get("answer", "")) for a in arms if a in arm_rows)
            ]
            print(row + "   " + "/".join(hits[:4]))
        total = {a: sum(covs.get(a, {}).values()) for a in arms}
        lens = {a: len(str(arm_rows[a].get("answer", ""))) for a in arms if a in arm_rows}
        print(f"{'合计':14s}" + "".join(f"{total.get(a, 0):>12d}" for a in arms))
        print(f"{'答案字数':14s}" + "".join(f"{lens.get(a, 0):>12d}" for a in arms))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
