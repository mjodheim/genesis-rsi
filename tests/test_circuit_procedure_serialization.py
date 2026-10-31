import copy
import itertools
import json

import pytest

from genesis import circuit_procedure as cp
from genesis.circuit_procedure import Procedure, ProcedureError


def test_procedure_replay_digest_survives_json_round_trip():
    procedure = Procedure(seed=1729)
    digest_before = procedure.replay_digest()
    record = procedure.to_record()
    original_record = copy.deepcopy(record)

    serialized = json.dumps(record, sort_keys=True, allow_nan=False)
    decoded_record = json.loads(serialized)
    replayed = Procedure.from_record(decoded_record)

    assert replayed.to_record() == decoded_record
    assert replayed.replay_digest() == digest_before
    assert procedure.replay_digest() == digest_before
    assert record == original_record
    assert json.loads(serialized) == decoded_record

    tampered_record = copy.deepcopy(decoded_record)
    assert "seed" in tampered_record
    tampered_record["seed"] = 1730

    with pytest.raises(ProcedureError):
        Procedure.from_record(tampered_record)

@pytest.mark.parametrize("seed", [0, 1729, -1, 2**80])
def test_seed_construction_is_reproducible(seed):
    first = Procedure(seed=seed)
    second = Procedure(seed=seed)

    cp.validate(first)
    assert first == second
    assert first.to_record() == second.to_record()
    assert first.to_record()["seed"] == seed

@pytest.mark.parametrize("seed", [True, False, 1.5, "1729", [], {}])
def test_invalid_seeds_are_rejected(seed):
    with pytest.raises(ProcedureError):
        Procedure(seed=seed)

@pytest.mark.parametrize("seed", [None, True, False, 1.5, "1729", [], {}])
def test_invalid_serialized_seeds_are_rejected_even_with_matching_digest(seed):
    record = Procedure(seed=1729).to_record()
    record["seed"] = seed
    body = {key: value for key, value in record.items() if key != "procedure_digest"}
    record["procedure_digest"] = cp.digest_of(body)

    with pytest.raises(ProcedureError):
        Procedure.from_record(record)

def test_unseeded_records_keep_their_existing_representation():
    procedure = cp.seed_procedure()
    record = cp.to_record(procedure)

    assert "seed" not in record
    assert Procedure.from_record(json.loads(json.dumps(record))) == procedure
    assert procedure.to_record() == record

def test_default_replay_matches_exhaustive_function_replay():
    procedure = Procedure(seed=1729)
    cases = list(itertools.product((0, 1), repeat=len(cp.TRAITS)))

    assert procedure.replay_digest() == cp.replay_digest(procedure, cases)
    assert procedure.replay_digest(iter(cases)) == cp.replay_digest(procedure, cases)

def test_deserialization_does_not_share_mutable_record_storage():
    procedure = Procedure(seed=1729)
    record = procedure.to_record()
    restored = Procedure.from_record(record)
    expected = restored.to_record()

    record["steps"][0][0] = (record["steps"][0][0] + 1) % len(cp.TRAITS)
    record["priority_outputs"][0] = 0

    assert restored == procedure
    assert restored.to_record() == expected
