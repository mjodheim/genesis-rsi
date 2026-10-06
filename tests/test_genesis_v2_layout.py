"""Genesis v2 package layout remains compatible with frozen historical imports."""

from genesis import (
    candidate_scheduler as legacy_candidate_scheduler,
    capability_gaps as legacy_capability_gaps,
    failure_driven_self_extension as legacy_self_extension,
    language_toolchains as legacy_toolchains,
    native_diagnosis as legacy_native_diagnosis,
    strategy_memory as legacy_strategy_memory,
    structural_operators as legacy_structural,
)
from genesis.languages import native_diagnosis, toolchains
from genesis.learning import capability_gaps, self_extension
from genesis.memory import strategy
from genesis.operators import structural
from genesis.runtime import candidate_scheduler


def test_v2_canonical_modules_back_legacy_public_symbols() -> None:
    assert legacy_toolchains.LanguagePack is toolchains.LanguagePack
    assert legacy_native_diagnosis.Probe is native_diagnosis.Probe
    assert legacy_structural.validate_operator is structural.validate_operator
    assert legacy_capability_gaps.diagnose is capability_gaps.diagnose
    assert legacy_self_extension.create_memory is self_extension.create_memory
    assert legacy_strategy_memory.rank_candidates is strategy.rank_candidates
    assert legacy_candidate_scheduler.fair_schedule is candidate_scheduler.fair_schedule
