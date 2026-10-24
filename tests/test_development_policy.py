import hashlib

import pytest

from genesis import development_policy as policy


JUDGE = hashlib.sha256(b"independent compiler and regression judge").hexdigest()


def observation(artifact, case_id, *, passed, used=1, false_positive=False, budget=4):
    return {
        "candidate_budget": budget,
        "candidates_used": used,
        "case_id": case_id,
        "false_positive": false_positive,
        "judge_digest": JUDGE,
        "passed": passed,
        "policy_digest": artifact["policy_digest"],
    }


def test_canonical_interoperability_vector_is_stable():
    artifact = policy.create()
    assert artifact["policy_digest"] == "822339855399daf1c3e2cb73e9777d225e7b96bf079b45861d1bb79b8bac58e1"
    assert policy.dumps(artifact).startswith('{"generation":0,"max_candidates":4,"max_files":1,')
    assert policy.validate(artifact) == artifact


def test_unknown_rules_fields_and_digest_drift_are_refused():
    artifact = policy.create()
    with pytest.raises(policy.DevelopmentPolicyError):
        policy.create(rule_order=[*policy.ALLOWED_RULES[:-1], "shell-command"])
    with pytest.raises(policy.DevelopmentPolicyError):
        policy.validate({**artifact, "command": "pytest"})
    with pytest.raises(policy.DevelopmentPolicyError):
        policy.validate({**artifact, "max_candidates": 8})


def test_descendants_are_bounded_direct_children_without_new_authority():
    parent = policy.create()
    children = policy.descendants(parent)
    assert len(children) == 6
    assert all(child["generation"] == 1 for child in children)
    assert all(child["parent_policy_digest"] == parent["policy_digest"] for child in children)
    assert all(set(child["rule_order"]) == set(policy.ALLOWED_RULES) for child in children)
    assert all(child["max_files"] == 1 for child in children)


def test_external_matched_evidence_can_promote_a_strictly_better_policy():
    parent = policy.create()
    candidate = policy.descendants(parent)[2]
    cases = ("compile-csharp", "compile-python", "refusal-ambiguous")
    evidence = {
        parent["policy_digest"]: [
            observation(parent, cases[0], passed=True, used=2),
            observation(parent, cases[1], passed=False, used=4),
            observation(parent, cases[2], passed=False, used=4, false_positive=True),
        ],
        candidate["policy_digest"]: [
            observation(candidate, cases[0], passed=True, used=1),
            observation(candidate, cases[1], passed=True, used=2),
            observation(candidate, cases[2], passed=False, used=1),
        ],
    }
    result = policy.select(parent, [candidate], evidence, case_ids=cases, matched_budget=4)
    assert result["adopted"] is True
    assert result["selected_policy"] == candidate
    assert result["selected_score"] == [2, 0, -4]
    assert result["parent_score"] == [1, -1, -10]


def test_incomplete_mismatched_or_self_attributed_evidence_is_refused():
    parent = policy.create()
    candidate = policy.descendants(parent)[0]
    cases = ("a", "b")
    complete = {
        parent["policy_digest"]: [observation(parent, "a", passed=True),
                                  observation(parent, "b", passed=False)],
        candidate["policy_digest"]: [observation(candidate, "a", passed=True),
                                     observation(candidate, "b", passed=True)],
    }
    broken = {key: list(value) for key, value in complete.items()}
    broken[candidate["policy_digest"]] = broken[candidate["policy_digest"]][:-1]
    with pytest.raises(policy.DevelopmentPolicyError):
        policy.select(parent, [candidate], broken, case_ids=cases, matched_budget=4)
    broken = {key: [dict(row) for row in value] for key, value in complete.items()}
    broken[candidate["policy_digest"]][0]["candidate_budget"] = 3
    with pytest.raises(policy.DevelopmentPolicyError):
        policy.select(parent, [candidate], broken, case_ids=cases, matched_budget=4)
    broken = {key: [dict(row) for row in value] for key, value in complete.items()}
    broken[candidate["policy_digest"]][0]["judge_digest"] = "self"
    with pytest.raises(policy.DevelopmentPolicyError):
        policy.select(parent, [candidate], broken, case_ids=cases, matched_budget=4)
