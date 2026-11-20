import pytest

from genesis.mira_coding_fitness import (
    Counts,
    TaskContext,
    _aggregate_attested_receipts,
    _count_attested_mcnemar_pairs,
)
from genesis.mira_policy_contract import BankExternalReceipt, CodingPolicy

@pytest.mark.parametrize("second_bank", ["a" * 64, "b" * 64], ids=["single", "mixed"])
def test_bank_identity_in_attested_aggregation_and_pairing(second_bank):
    policy = CodingPolicy.create(
        localization="task-context",
        tool_order=["inspect", "edit", "test"],
        trial_and_repair_strategy="At most 10 trials with repair",
        task_budget={
            "models": ["offline-test-model"],
            "tokens": 1000,
            "proposals": 10,
            "time_seconds": 60,
        },
    )
    budget = {
        "models": ["offline-test-model"],
        "tokens": 100,
        "proposals": 1,
        "time_seconds": 2,
    }
    contexts = [
        TaskContext("a", "python", "judge-a", "a" * 64, budget, policy),
        TaskContext("b", "rust", "judge-b", second_bank, budget, policy),
    ]
    attestations = {}
    arms = []
    for run_id, verdicts in (("left", (True, False)), ("right", (True, True))):
        receipts = []
        for context, verdict in zip(contexts, verdicts):
            receipt = BankExternalReceipt.create(
                policy_sha256=policy.sha256,
                bank_sha256=context.bank_fingerprint,
                task_id=context.task_id,
                judge_id=context.judge,
                consumed_budget=context.consumed_budget,
                declared_result=verdict,
            )
            attestations[
                run_id,
                context.judge,
                context.bank_fingerprint,
                policy.sha256,
                context.task_id,
            ] = receipt.envelope.sha256
            receipts.append(receipt)
        arms.extend((receipts, contexts))

    if second_bank != contexts[0].bank_fingerprint:
        for run_id, receipts in (("left", arms[0]), ("right", arms[2])):
            with pytest.raises(ValueError, match="exactly one bank fingerprint"):
                _aggregate_attested_receipts(
                    receipts, contexts=contexts, run_id=run_id, attestations=attestations
                )
        with pytest.raises(ValueError, match="exactly one bank fingerprint"):
            _count_attested_mcnemar_pairs(
                *arms, left_run_id="left", right_run_id="right", attestations=attestations
            )
        return

    fitness = _aggregate_attested_receipts(
        arms[0], contexts=contexts, run_id="left", attestations=attestations
    )
    assert fitness.overall == Counts(1, 2)
    assert fitness.by_language == {"python": Counts(1, 1), "rust": Counts(0, 1)}
    pairs = _count_attested_mcnemar_pairs(
        *arms, left_run_id="left", right_run_id="right", attestations=attestations
    )
    assert pairs.overall == (1, 0, 1, 0)
    assert pairs.by_language == {"python": (1, 0, 0, 0), "rust": (0, 0, 1, 0)}
