from pathlib import Path

import pytest

from genesis.operators import universal


def _python_operator() -> dict:
    return universal.learn_from_validated_pair(
        "def f(items):\n    return items[1]\n",
        "def f(items):\n    return items[0]\n",
        source_path="source.py",
        source_result_digest="validated-python-pass",
    )


def test_g2_learns_language_neutral_subscript_operation_from_python() -> None:
    operator = _python_operator()

    assert operator["source_language"] == "python"
    assert operator["semantic_role"] == "subscript_index"
    assert operator["from_token"] == {"kind": "number", "value": "1"}
    assert operator["to_token"] == {"kind": "number", "value": "0"}
    assert operator["external_model_calls_for_learning"] == 0


def test_g2_materializes_one_learned_operation_in_three_other_languages() -> None:
    operator = _python_operator()
    cases = {
        "A.java": (
            "class A { int f(int[] values) { return values[1]; } }\n",
            "class A { int f(int[] values) { return values[0]; } }\n",
        ),
        "a.ts": (
            "function f(data: number[]) { return data[1]; }\n",
            "function f(data: number[]) { return data[0]; }\n",
        ),
        "A.cs": (
            "class A { int F(int[] values) { return values[1]; } }\n",
            "class A { int F(int[] values) { return values[0]; } }\n",
        ),
    }

    for path, (source, expected) in cases.items():
        assert expected in universal.materialize_source(
            source,
            path=path,
            operator=operator,
        )


def test_g2_project_generation_records_cross_language_causal_provenance(tmp_path: Path) -> None:
    operator = _python_operator()
    fixtures = {
        "A.java": "class A { int f(int[] values) { return values[1]; } }\n",
        "a.ts": "function f(data: number[]) { return data[1]; }\n",
        "A.cs": "class A { int F(int[] values) { return values[1]; } }\n",
    }
    for path, source in fixtures.items():
        (tmp_path / path).write_text(source, encoding="utf-8")

    result = universal.generate(tmp_path, [operator])
    targets = {
        item["provenance"]["target_language"]
        for item in result["candidates"]
    }

    assert result["external_model_calls"] == 0
    assert result["candidate_count"] == 3
    assert targets == {"java", "typescript", "csharp"}
    assert all(
        item["provenance"]["source_language"] == "python"
        and item["provenance"]["source_result_digest"] == "validated-python-pass"
        for item in result["candidates"]
    )


def test_g2_rejects_tampered_operator() -> None:
    operator = _python_operator()
    forged = dict(operator)
    forged["source_result_digest"] = "forged"

    with pytest.raises(ValueError, match="does not reproduce its digest"):
        universal.materialize_source(
            "function f(data: number[]) { return data[1]; }\n",
            path="a.ts",
            operator=forged,
        )
