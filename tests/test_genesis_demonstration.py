"""Lock the end-to-end Genesis demonstration.

The stopping criterion is not that the components exist. It is that **one lineage** measures itself,
diagnoses itself, transforms itself, verifies the transformation, adopts or rejects it on evidence,
keeps what it learned, extends the machinery that enables later transformations, changes form, and
goes on evolving in the new form. These tests assert each of those on the same run.

They also assert something the earlier version could not: that the *runtime* performs those
transitions. The demonstration script used to call the probes, assign `genesis.state` and append the
journal entries itself, so what the run showed was a person calling the pieces in the right order.
The script now supplies a world, a mechanism that returns declarative intents, and a renderer;
everything below reads a record `genesis.controller.run` produced.
"""
from __future__ import annotations

import pytest

from genesis import development_bodies as bodies
from genesis import trust_root as tr
from genesis.artifacts import ConfiguredBody
from genesis.sandbox import run_candidate
from scripts.run_genesis_demonstration import TASKS, demonstrate


@pytest.fixture(scope="module")
def record(tmp_path_factory):
    return demonstrate(tmp_path_factory.mktemp("genesis-demonstration-state"))


def _steps(record, intent):
    return [step for step in record["run"]["steps"] if step["intent"] == intent]


def _named(record, name):
    for step in _steps(record, "Transform"):
        if step.get("name") == name:
            return step
    raise AssertionError("the demonstration never proposed %r" % name)


def _only(record, intent):
    matching = _steps(record, intent)
    assert len(matching) == 1, "expected exactly one %s intent, saw %d" % (intent, len(matching))
    return matching[0]


# -- the demonstration, step by step --------------------------------------------------------------

def test_the_demonstration_claims_nothing_scientific(record):
    assert record["development"] is True
    assert record["is_a_scientific_observation"] is False
    assert record["advances_a_generality_gate"] is False
    assert record["frozen"] is False


def test_the_architecture_is_sequenced_by_the_runtime(record):
    """The property R2-13 asked for: the transitions are the runtime's, not the driver's."""
    assert record["architecture_sequenced_by"] == "genesis.controller.run"
    assert record["run"]["schema"] == "genesis-controller-run-v1"
    assert [step["intent"] for step in record["run"]["steps"]][-1] == "stop"


def test_a_rejection_does_not_end_the_run_and_is_kept(record):
    step = _named(record, "regressed")
    assert step["accepted"] is False
    assert step["lineage"]["observations_kept"] == 1
    # The run continued: later intents exist and later acceptances happened.
    assert len(record["run"]["steps"]) > 1


def test_a_transformation_is_adopted_on_evidence(record):
    step = _named(record, bodies.ACQUIRED_COMPONENT)
    assert step["accepted"] is True
    assert step["lineage"]["acquisitions"] == 1


def test_the_evidence_is_not_the_candidate_s_own_account_of_itself(record):
    """The trust root recomputing a tally is worth nothing if the candidate wrote the rows.

    `tests/test_genesis_loop.py` carries the load-bearing pair: one body that wins everything when
    it grades itself and scores zero when the parent grades. This asserts the demonstration runs on
    the second footing.
    """
    for step in _steps(record, "Transform"):
        assert step["outcomes_are_self_reported"] is False


def test_the_lineage_names_a_component_class_it_did_not_have(record):
    """The first authored ceiling, opened by the lineage rather than by editing a tuple."""
    step = _only(record, "AcquireComponent")
    assert step["acquired"] is True
    assert step["registry_exhausted"] is True
    assert step["probed"] == ["operator_table", "signal_interface"]
    assert step["registry_after"][-1] == "joint_registry"
    assert record["run"]["final_components"] == [
        "operator_table",
        "signal_interface",
        "joint_registry",
    ]


def test_the_probes_were_composed_and_run_rather_than_consulted(record):
    """The third ceiling. No host callable answers 'does this component resolve the demand'.

    Compositions are built by the lineage, executed in isolation, and judged on raw per-task
    outcomes. `tests/test_genesis_probe.py` carries the load-bearing check that the finding follows
    the data; this asserts the demonstration actually goes through that path.
    """
    step = _only(record, "AcquireComponent")
    assert step["probe_is_experimental_not_an_oracle"] is True
    assert step["compositions_run"] > 0, "a certificate must rest on probes that ran"
    # Exhaustion alone would only be a failed search.
    assert step["reachable_with_wider_operations"] is True
    assert step["composition_the_lineage_found"] == ["double", "increment"]


def test_the_lineage_extends_its_own_diagnostic_vocabulary(record):
    """The second ceiling: extended on a *measured* confusable pair, not on a whim.

    Both demands read identically through the lineage's per-component vocabulary and their causes
    differ, and both halves of that come from probes rather than from a callable that was told the
    answer.
    """
    step = _only(record, "SeparateVocabulary")
    assert step["extended"] is True
    assert step["shared_prior_row"] == [False, False]
    assert step["limiting_components"] == ["operator_table", "signal_interface"]
    assert step["resolving_operations"] == [
        ["increment", "negate", "double"],
        ["double", "square", "negate"],
    ]
    assert step["vocabulary_after"][-1] == "requires_increment"


def test_neither_ceiling_is_held_up_by_an_oracle_any_more(record):
    """Both steps now run experiments, and the record has to say which is which.

    This assertion is the one that would fail first if a host-written shortcut were reintroduced
    into either path, which is why it reads the flags rather than trusting the step names.
    """
    assert _only(record, "AcquireComponent")["probe_is_experimental_not_an_oracle"] is True
    vocabulary_step = _only(record, "SeparateVocabulary")
    assert vocabulary_step["rests_on_a_host_supplied_oracle"] is False
    assert vocabulary_step["feature_read_out_of_the_measurements"] == "requires_increment"


def test_the_substrate_is_discovered_and_the_lineage_arrives_intact(record):
    step = _only(record, "Migrate")
    assert step["found"] == ["read", "list"]
    assert step["missing"] == ["write", "transact"]
    assert step["journal_continues"] is True
    assert step["nothing_lost"] is True


def test_the_lineage_evolves_again_in_its_new_form(record):
    """Transported intelligence rather than transported output. This is the whole objective."""
    outcome = record["run"]["metamorphosis"]
    assert outcome["succeeded"] is True
    assert outcome["accepted_after_migration"] == 3
    assert outcome["is_transported_intelligence_rather_than_transported_output"] is True


def test_the_lineage_accepts_three_transformations_not_one(record):
    """A single acceptance shows the runtime works. Three show the lineage is still going."""
    accepted = [step for step in _steps(record, "Transform") if step["accepted"]]
    assert len(accepted) == 4
    assert record["run"]["final_generation"] == 4


def test_the_translation_is_verified_rather_than_assumed(record):
    """State arriving intact says nothing about what the arrival can do.

    `carried_intact` compares components, certificates and acquisitions. A translation could drop
    every capability and still pass it, because nothing being counted would have been lost.
    """
    step = _only(record, "Migrate")
    assert step["capability_measured"] is True
    assert step["capability_preserved"] is True
    assert step["solved_before_and_after"] == [4, 4]


@pytest.mark.parametrize(
    "candidate, depends_on",
    [
        ("carrier_index", "joint_registry"),
        ("carrier_index_ii", "carrier_index"),
        ("carrier_index_iii", "carrier_index_ii"),
    ],
)
def test_each_generation_needed_the_one_before_it(record, candidate, depends_on):
    """Three consecutive ablations, each run inside the cycle that accepted the candidate."""
    causal = _named(record, candidate)["causal_dependency"]
    assert causal["depends_on"] == depends_on
    assert causal["established"] is True
    assert causal["arm_run"] is True
    assert causal["solved_without_acquisition"] < causal["solved_with_acquisition"]
    # Without this the "ablation" is the parent arm, and the comparison merely repeats the verdict
    # that accepted the candidate.
    assert causal["ablated_arm_differs_from_the_parent_arm"] is True
    assert causal["why"] == ""


@pytest.mark.parametrize(
    "candidate, depends_on",
    [
        ("carrier_index", "joint_registry"),
        ("carrier_index_ii", "carrier_index"),
        ("carrier_index_iii", "carrier_index_ii"),
    ],
)
def test_the_ablation_arm_was_built_by_the_runtime_not_supplied_to_it(record, candidate, depends_on):
    """The counterfactual is derived from the candidate, so it cannot be the proposer's own choice.

    The loop called this a permanent obligation of the runtime while a script was doing it; then the
    cycle ran it, on whichever arm the proposal handed over. Now the arm is one the runtime built and
    checked against the candidate, and the record carries both digests so the claim can be re-derived
    rather than believed.
    """
    causal = _named(record, candidate)["causal_dependency"]
    assert causal["arm_derived_by_the_runtime"] is True
    assert causal["caller_supplied_arm_used_as_evidence"] is False
    assert causal["caller_supplied_arm_offered"] is False
    assert causal["candidate_artifact_digest"] != causal["ablated_artifact_digest"]


def test_the_lineage_reports_a_number_and_does_not_convert_it_into_a_verdict(record):
    """Four acquisitions, three established links: the first depended on nothing earlier.

    The previous version turned `links >= 2` into "a chain rather than a sequence" — a threshold set
    at the smallest number that permits the word. Whether n links is recursion is not a question the
    thing being measured gets to settle, so the record reports the number and says so.
    """
    chain = record["run"]["causal_chain"]
    assert chain["acquisitions"] == 4
    assert chain["established_links"] == 3
    assert chain["makes_no_recursion_claim"] is True
    assert "is_a_chain_rather_than_a_sequence" not in chain


@pytest.mark.parametrize(
    "candidate_factory, removed",
    [
        ("migrated_improved_body", "ACQUIRED_COMPONENT"),
        ("migrated_further_body", "SECOND_ACQUISITION"),
        ("migrated_fourth_body", "THIRD_ACQUISITION"),
    ],
)
def test_an_ablated_arm_is_its_candidate_minus_one_acquisition(candidate_factory, removed):
    """The runtime's own derivation, checked field by field on the built bodies.

    This used to compare a candidate fixture against a hand-written twin, and a reviewer had to take
    on trust that the two differed in one field. The arm is now produced by the same call the cycle
    makes, so what is checked here is the derivation rather than a pair of definitions.
    """
    factory = getattr(bodies, candidate_factory)
    assert isinstance(factory, ConfiguredBody)
    arm = factory.without(getattr(bodies, removed))
    candidate, ablated = factory(), arm()
    assert ablated.solves == candidate.solves
    assert ablated.operation_names == candidate.operation_names
    assert ablated.routed == candidate.routed
    assert candidate.capabilities - ablated.capabilities == {getattr(bodies, removed)}
    assert ablated.capabilities < candidate.capabilities


def test_the_ablated_generation_breaks_rather_than_falling_back_to_its_parent():
    """What makes the removal real: the candidate reaches for a component that is not there.

    t2, t3 and the newly gained t4 are `error` rather than `unsolved` because the body raises
    instead of returning a wrong answer. The t4 loss is now load-bearing: it proves the ablation
    breaks work newly gained by this generation, not only work retained from its parent.
    """
    outcomes = {
        row["task_id"]: row["outcome"]
        for row in run_candidate(
            bodies.migrated_improved_body.without(bodies.ACQUIRED_COMPONENT),
            TASKS,
            tr.Isolation(),
            grade=bodies.grade,
        )["outcomes"]
    }
    assert outcomes == {
        "t0": "solved",
        "t1": "solved",
        "t2": "error",
        "t3": "error",
        "t4": "error",
        "t5": "unsolved",
        "t6": "unsolved",
        "t7": "unsolved",
    }


def test_the_whole_lineage_comes_back_from_disk(record):
    survival = record["survives_process_death"]
    assert survival["state_digest_matches"] is True
    assert survival["journal_head_matches"] is True
    assert survival["journal_length"] > 10


def test_the_journal_is_one_continuous_descent_through_the_migration(record):
    kinds = record["journal_kinds"]
    assert kinds[0] == "seed"
    assert "candidate_rejected" in kinds
    assert "component_acquired" in kinds
    assert "vocabulary_extended" in kinds
    assert "migration" in kinds
    # Evolution continued after the change of form.
    assert "candidate_accepted" in kinds[kinds.index("migration") :]


def test_the_demonstration_is_reproducible(record, tmp_path):
    assert demonstrate(tmp_path / "replay")["record_digest"] == record["record_digest"]
