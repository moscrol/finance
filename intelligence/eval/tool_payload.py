"""Attribute a failed fact to retrieve vs synthesize from tool_result meta.

Does not import the product runtime. Callers pass the already-persisted
``tool_result`` dicts (ledger events or an observation sidecar).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def attribute_failed_fact(
    *,
    expected_field: str,
    expected_dataset: str | None,
    tool_results: Sequence[Mapping[str, Any]],
) -> str:
    """Return ``retrieve``, ``synthesize``, or ``unknown``.

    - ``synthesize``: the field name appeared in some ``payload_field_names``
      **and** ``expected_dataset`` was declared and matched (data was fetched
      from the right table, the answer did not write it).
    - ``retrieve``: the expected dataset/caliber never showed up, a different
      dataset was served (wrong table, including same column names on the wrong
      table — A5), or the field name appeared nowhere.
    - ``unknown``: no payload meta on the results (old artifacts), **or** the
      field name matched while no ``expected_dataset`` was declared.

    That last ``unknown`` is the point of this function, so do not "simplify" it
    into ``synthesize``. A column name is not unique to a table: A5 wants
    ``limit_up_count`` from ``fact_theme_limit_heat_daily`` but the episode
    fetched ``fact_mainline_sector_daily``, which has a column of the same name.
    Without a declared caliber this looked exactly like "fetched but not
    written", and the old code returned a confident ``synthesize`` for what is
    really a ``retrieve`` miss — pointing effort at the wrong layer. Recognising
    nothing is the honest answer here; see the repo's "认不出来就 fail closed".
    """

    field = str(expected_field or "").strip()
    expected = str(expected_dataset or "").strip()
    saw_meta = False
    field_hits = False
    datasets: list[str] = []
    for item in tool_results:
        names = item.get("payload_field_names")
        dataset = item.get("dataset")
        caliber = item.get("caliber")
        if names is None and dataset is None and caliber is None:
            continue
        saw_meta = True
        if dataset:
            datasets.append(str(dataset))
        if caliber:
            datasets.append(str(caliber))
        name_list = [str(n) for n in (names or ())]
        if field and (
            field in name_list
            or field.split(".")[-1] in name_list
        ):
            field_hits = True
    if not saw_meta:
        return "unknown"
    if expected and not any(_dataset_matches(expected, value) for value in datasets):
        return "retrieve"
    if field_hits:
        if not expected:
            return "unknown"
        return "synthesize"
    return "retrieve"


def _dataset_matches(expected: str, observed: str) -> bool:
    if not expected or not observed:
        return False
    if expected == observed:
        return True
    return expected in observed or observed in expected
