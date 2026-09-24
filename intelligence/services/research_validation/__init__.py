"""方法验证与真实前向概率实验（spec 03）。

对外只暴露六个服务函数、Repository 与合同工具。06 接线时：

    repo = Repository(user_space(user).root / "research_validation", owner_user_id=user)
    freeze_study(owner=user, repository=repo, now=trusted_now, protocol_input=body)

本包属领域层 ``services/``：不 import ``intelligence.runtime``、不 import ``intelligence.eval``。
"""

from .baseline import (
    BASELINE_RECIPE_HASH,
    TWO_BUCKET_RECIPE,
    TWO_BUCKET_RECIPE_HASH,
    OutcomeRow,
    compute_baseline,
    smoothed_probability,
    two_bucket_probabilities,
)
from .contracts import (
    Calendar,
    ConflictError,
    ContractError,
    Gap,
    OwnerMismatch,
    canonical_bytes,
    derive_case_id,
    digest,
    outcome_identity,
)
from .repository import Repository
from .scoring import DailyDelta, PairSample, brier, calibration_buckets, daily_deltas, paired_readout, strict_bools
from .service import (
    OutcomeSource,
    PitVerifier,
    RegisterResult,
    SettleResult,
    evaluate_study,
    freeze_study,
    read_receipt,
    record_exposure,
    register_forecasts,
    settle_outcomes,
)

__all__ = [
    "BASELINE_RECIPE_HASH",
    "Calendar",
    "ConflictError",
    "ContractError",
    "DailyDelta",
    "Gap",
    "OutcomeRow",
    "OutcomeSource",
    "OwnerMismatch",
    "PairSample",
    "PitVerifier",
    "RegisterResult",
    "Repository",
    "SettleResult",
    "TWO_BUCKET_RECIPE",
    "TWO_BUCKET_RECIPE_HASH",
    "brier",
    "calibration_buckets",
    "canonical_bytes",
    "compute_baseline",
    "daily_deltas",
    "derive_case_id",
    "digest",
    "evaluate_study",
    "freeze_study",
    "outcome_identity",
    "paired_readout",
    "read_receipt",
    "record_exposure",
    "register_forecasts",
    "settle_outcomes",
    "smoothed_probability",
    "strict_bools",
    "two_bucket_probabilities",
]
