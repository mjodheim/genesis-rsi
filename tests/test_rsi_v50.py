"""Exact semantic decoding, native/reference agreement and model boundaries."""
import base64
import copy
import itertools
import json

import pytest

from experiment.rsi_v32 import storage
from experiment.rsi_v50 import development, model, native


@pytest.mark.parametrize("op", (1, 2, 3, 4))
def test_native_codec_has_distinct_output_language_and_exact_inverse(op):
    rows = native.execute((op,))
    assert native.validate_outputs((op,), rows)
    for text, row in zip(native.TEXTS, rows):
        output = native.unpack(row["value"])
        assert native.classify(text) is None
        assert native.classify(output) == op
        assert native.inverse(op, output) == text
    if op == 4:
        assert base64.b64decode(native.unpack(rows[0]["value"]))[9] == 255


def test_all_short_native_words_are_behavior_distinct_without_hash_identity():
    seen = set()
    words = ((), *(w for n in range(1, 4) for w in itertools.product(range(1, 5), repeat=n)))
    for word in words:
        rows = native.execute(word, isolated=False)
        assert native.validate_outputs(word, rows)
        output = native.unpack(rows[0]["value"])
        recovered, base = native.decode(output)
        assert recovered == word and base == native.TEXTS[0]
        assert output not in seen
        seen.add(output)
    assert len(seen) == 85


@pytest.mark.parametrize("field", ("primitive_visits", "encoder_interface_bytes", "output_bytes"))
def test_native_work_and_transport_tampering_are_rejected(field):
    rows = native.execute((2, 3), isolated=False)
    bad = copy.deepcopy(rows)
    bad[0]["value"][field] += 1
    with pytest.raises(ValueError):
        native.validate_outputs((2, 3), bad)


def test_isolated_worker_receives_only_public_inputs(monkeypatch):
    original, payloads = native.subprocess.run, []

    def capture(*args, **kwargs):
        if "input" in kwargs:
            payloads.append(json.loads(kwargs["input"]))
        return original(*args, **kwargs)

    monkeypatch.setattr(native.subprocess, "run", capture)
    native.execute((1, 4))
    assert payloads
    assert all(set(case) == {"operation", "data"} and set(case["data"]) == {"text"}
        for payload in payloads for case in payload["operations"])


def test_model_constructs_large_words_under_constant_query_bound():
    library = [(op,) * 128 for op in range(1, 5)]
    target = library[-1] + library[-1]
    result = model.search(library, model.exact_equality_oracle(target))
    assert result["solved"] and result["word"] == target
    assert len(result["calls"]) == 17
    assert len(result["calls"]) + 1 + 4 <= 22  # Identity and optional paid screens.
    # Symbolic queries above are not isolated native executions or a fresh assay.


def test_incomplete_or_misaligned_library_invalidates_continuation_premise():
    with pytest.raises(ValueError, match="four distinct"):
        model.products([(1,), (2,)])
    with pytest.raises(ValueError, match="equal-length"):
        model.products([(1,), (2,), (3,), (4, 4)])


def test_nonempty_domain_and_untrusted_genotype_boundary():
    assert all(native.classify(text) is None for text in native.TEXTS)
    with pytest.raises(ValueError, match="Empty"):
        native.reference((), "")
    with pytest.raises(ValueError):
        native.render((True,))
    with pytest.raises(ValueError, match="Wrong"):
        native.inverse(1, "H4sIinvalid")


def test_completed_or_pending_fixture_directory_refuses_another_attempt(tmp_path):
    with pytest.raises(FileExistsError, match="consumed"):
        development.collect(tmp_path)


def test_instrument_failure_consumes_reservation_without_retry(tmp_path, monkeypatch):
    words = ((), (1,))
    monkeypatch.setattr(development, "WORDS", words)
    monkeypatch.setattr(development, "manifest", lambda: {"scope": "unit-fixture", "words": [[], [1]]})
    real, counts = native.execute, {}

    def execute(ops, **kwargs):
        counts[ops] = counts.get(ops, 0) + 1
        if not ops:
            raise RuntimeError("Public unit instrument failure")
        return real(ops, isolated=False)

    monkeypatch.setattr(native, "execute", execute)
    root = tmp_path / "fixture"
    report = development.collect(root, workers=1)
    assert counts == {(): 1, (1,): 2}
    assert report["charged_calls"] == 4 and report["executed_requests"] == 3
    assert not report["development_validated"] and not report["fresh_population"]
    assert not report["l9_general_open_ended_passed"] and not report["l10_independent_passed"]
    row = storage.read_json(root / "word-0000/RESULT.json")
    assert row["failure"] and row["inverse_decoded_word"] is None


def test_readonly_checker_rejects_work_accounting_mutation(tmp_path, monkeypatch):
    monkeypatch.setattr(development, "WORDS", ((1,),))
    monkeypatch.setattr(development, "manifest", lambda: {"scope": "unit-fixture", "words": [[1]]})
    monkeypatch.setattr(development, "verify_manifest", lambda value: None)
    real = native.execute
    monkeypatch.setattr(native, "execute", lambda ops, **kwargs: real(ops, isolated=False))
    root = tmp_path / "fixture"
    development.collect(root, workers=1)
    assert development.check(root)["development_validated"]
    path = root / "word-0000/RESULT.json"
    value = storage.read_json(path)
    value["primitive_visits"] += 1
    path.unlink()  # Disposable hostile test fixture only.
    storage.publish_json(path, value)
    with pytest.raises(ValueError, match="work"):
        development.check(root)
