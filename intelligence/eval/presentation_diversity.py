"""Advisory anti-template metrics for batches of research answers.

This is intentionally an offline signal, not a production blocker.  It
measures structural similarity (heading sequence + paragraph shape) while
ignoring citations, dates and numbers.  High similarity tells reviewers that
answers may be filling the same form; it says nothing about factual quality.
"""
from __future__ import annotations

import itertools
import re
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from typing import Sequence


_CITATION_RE = re.compile(r"\[[A-Z]\d+(?:\s*[,，]\s*[A-Z]\d+)*\]")
_MARKER_RE = re.compile(r"<!--.*?-->")
_NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?(?:%|亿元|万|元|点|只|家|日|周|月|年)?")


@dataclass(frozen=True)
class SimilarPair:
    left_id: str
    right_id: str
    similarity: float


@dataclass(frozen=True)
class DiversityReport:
    answer_count: int
    pair_count: int
    mean_template_similarity: float
    max_template_similarity: float
    high_similarity_pairs: tuple[SimilarPair, ...]
    threshold: float
    advisory: bool = True

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["high_similarity_pairs"] = [asdict(item) for item in self.high_similarity_pairs]
        return value


def heading_sequence(answer: str) -> tuple[str, ...]:
    return tuple(
        re.sub(r"\s+", "", line.lstrip("#").strip()).lower()
        for line in str(answer or "").splitlines()
        if line.lstrip().startswith("#") and line.lstrip("#").strip()
    )

def _paragraph_shape(answer: str) -> str:
    shapes: list[str] = []
    for raw in str(answer or "").splitlines():
        line = _MARKER_RE.sub("", _CITATION_RE.sub("", raw)).strip()
        if not line:
            continue
        if line.startswith("#"):
            shapes.append("H")
            continue
        if line.startswith(("-", "*")):
            prefix = "B"
        elif line.startswith("|"):
            prefix = "T"
        else:
            prefix = "P"
        normalized = _NUMBER_RE.sub("N", line)
        length_bucket = min(5, max(1, len(normalized) // 40 + 1))
        shapes.append(f"{prefix}{length_bucket}")
    return " ".join(shapes)


def template_similarity(left: str, right: str) -> float:
    left_headings = " / ".join(heading_sequence(left))
    right_headings = " / ".join(heading_sequence(right))
    heading_score = SequenceMatcher(None, left_headings, right_headings).ratio()
    shape_score = SequenceMatcher(
        None,
        _paragraph_shape(left),
        _paragraph_shape(right),
    ).ratio()
    weight = 0.7 if left_headings and right_headings else 0.25
    return round(weight * heading_score + (1 - weight) * shape_score, 4)


def audit_presentation_diversity(
    answers: Sequence[tuple[str, str]],
    *,
    threshold: float = 0.82,
) -> DiversityReport:
    pairs: list[SimilarPair] = []
    scores: list[float] = []
    for (left_id, left), (right_id, right) in itertools.combinations(answers, 2):
        score = template_similarity(left, right)
        scores.append(score)
        if score >= threshold:
            pairs.append(SimilarPair(left_id, right_id, score))
    return DiversityReport(
        answer_count=len(answers),
        pair_count=len(scores),
        mean_template_similarity=round(sum(scores) / len(scores), 4) if scores else 0.0,
        max_template_similarity=max(scores, default=0.0),
        high_similarity_pairs=tuple(sorted(pairs, key=lambda item: -item.similarity)),
        threshold=threshold,
    )
