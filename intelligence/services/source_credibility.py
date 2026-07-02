"""信息源可信度评分（P2-12）：同一句话"来自哪里"比"说了什么"更重要.

对应 docs/learning/finance-agent-skill-expansion-brainstorm.md P2-12：
对来源类型本身打分（0~1），解决"晨汇转述被当成公告"的错位问题；
分数可反哺 RAG rerank（重排时按 score 加权），也用于回答里的
来源可信度标注。纯规则、确定性；不改变检索本身。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# (来源类型, 分数, 判别特征词)。按手册排序：官方公告 > 年报/定期报告 >
# 互动易 > 卖方深度 > 晨汇转述 > PDF OCR > 截图/社媒。
SOURCE_TYPE_SCORES: list[tuple[str, float, tuple[str, ...]]] = [
    ("official_announcement", 0.95, ("公告", "中标公告", "交易所披露", "监管披露")),
    ("periodic_report", 0.9, ("年报", "半年报", "季报", "定期报告", "招股书")),
    ("exchange_interaction", 0.8, ("互动易", "e互动", "投资者关系", "调研纪要")),
    ("sellside_deep", 0.6, ("深度报告", "首次覆盖", "深度研究", "研报")),
    ("morning_note", 0.45, ("晨汇", "晨会", "早评", "转述")),
    ("pdf_ocr", 0.35, ("OCR", "扫描件", "图片研报")),
    ("social_screenshot", 0.2, ("截图", "社媒", "微博", "雪球", "股吧", "小作文")),
]

UNKNOWN_TYPE = "unknown"
UNKNOWN_SCORE = 0.3  # 未识别来源：略高于社媒、低于 OCR，先当弱证据用


@dataclass(frozen=True)
class SourceCredibility:
    source_type: str
    score: float
    matched: str = ""  # 命中的特征词

    def to_dict(self) -> dict[str, Any]:
        return {"source_type": self.source_type, "score": self.score, "matched": self.matched}


def score_source(text: str) -> SourceCredibility:
    line = str(text or "")
    for source_type, score, terms in SOURCE_TYPE_SCORES:
        for term in terms:
            if term in line:
                return SourceCredibility(source_type=source_type, score=score, matched=term)
    return SourceCredibility(source_type=UNKNOWN_TYPE, score=UNKNOWN_SCORE)


def rerank_by_credibility(
    hits: list[tuple[str, float]],
    *,
    weight: float = 0.3,
) -> list[tuple[str, float, SourceCredibility]]:
    """按 `(1-weight)*检索分 + weight*来源可信度` 重排命中列表。

    hits: [(text, retrieval_score∈0~1), ...]；返回按混合分降序。
    这是 rerank 的最轻量形态：不引入模型，只引入先验（来源质量）。
    """
    scored = []
    for text, retrieval_score in hits or []:
        cred = score_source(text)
        mixed = round((1 - weight) * float(retrieval_score) + weight * cred.score, 6)
        scored.append((text, mixed, cred))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored
