"""Tests de l'archive de lignée de circuit (trace SYNTHÉTIQUE uniquement).

Aucun réseau, aucun modèle. Les données ci-dessous sont synthétiques :
elles ne représentent aucun résultat réel.
"""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "scripts"
    / "archive_circuit_lineage_evidence.py"
)
_spec = importlib.util.spec_from_file_location(
    "archive_circuit_lineage_evidence", SCRIPT
)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

SYNTHETIC_TRACE = {
    "plan_digest": "synthetic-plan-digest",
    "scale": "synthetic-scale",
    "seeds": [11, 12],
    "generations": 2,
    "arms": {
        "synthetic_arm_a": [
            {
                "seed": 11,
                "procedure_initial": {"steps": ["s1", "s2"], "note": "synthetique"},
                "procedure_final": {"steps": ["s1", "s2", "s3"]},
                "generations": [
                    {
                        "spend": 1.5,
                        "spent": 1.5,
                        "limit": 10,
                        "procedure_digest": "d0",
                        "transmission": {"digest": "d1"},
                    },
                    {
                        "spend": 2,
                        "spent": 3.5,
                        "limit": 10,
                        "procedure_digest": "d1",
                        "transmission": {"digest": "d2"},
                    },
                ],
            },
            {
                "seed": 12,
                "generations": [
                    {
                        "spend": 0,
                        "spent": 0,
                        "procedure_digest": "e0",
                        "transmission": {"digest": "e1"},
                    }
                ],
            },
        ],
        "synthetic_arm_b": [
            {
                "seed": 11,
                "generations": [
                    {
                        "spend": 4,
                        "spent": 4,
                        "limit": 10,
                        "procedure_digest": "f0",
                        "transmission": {"digest": "f1"},
                    }
                ],
            }
        ],
    },
}


def _write_trace(tmp_path):
    path = tmp_path / "synthetic_trace.json"
    path.write_bytes(json.dumps(SYNTHETIC_TRACE, indent=1).encode("utf-8"))
    return path


def _run(tmp_path, name="archive.json", folder="results"):
    trace = _write_trace(tmp_path)
    out = tmp_path / folder / name
    mod.archive(trace, out, root=tmp_path)
    return trace, out, json.loads(out.read_text(encoding="utf-8"))


def test_synthetic_procedures_and_spend_preserved_exactly(tmp_path):
    _, _, data = _run(tmp_path)
    for arm, runs in SYNTHETIC_TRACE["arms"].items():
        assert len(data["arms"][arm]) == len(runs)
        for run_in, run_out in zip(runs, data["arms"][arm]):
            assert run_out["seed"] == run_in["seed"]
            for key in ("procedure_initial", "procedure_final"):
                if key in run_in:
                    assert run_out[key] == run_in[key]
                else:
                    assert key not in run_out
            assert len(run_out["generations"]) == len(run_in["generations"])
            for gen_in, gen_out in zip(run_in["generations"], run_out["generations"]):
                for key, value in gen_in.items():
                    assert gen_out[key] == value
                    assert type(gen_out[key]) is type(value)
    assert data["provenance"]["plan_digest"] == "synthetic-plan-digest"
    assert data["provenance"]["seeds"] == [11, 12]
    assert data["provenance"]["scale"] == "synthetic-scale"
    assert data["provenance"]["generations"] == 2


def test_absent_fields_are_reported_not_invented(tmp_path):
    _, _, data = _run(tmp_path)
    paths = {item["path"] for item in data["absent"]}
    a = '$.arms["synthetic_arm_a"]'
    b = '$.arms["synthetic_arm_b"]'
    assert "$.machinery_commit" in paths
    assert f"{a}[1].procedure_initial" in paths
    assert f"{a}[1].procedure_final" in paths
    assert f"{a}[1].generations[0].limit" in paths
    assert f"{b}[0].procedure_initial" in paths
    assert f"{b}[0].procedure_final" in paths
    assert "$.plan_digest" not in paths
    assert "machinery_commit" not in data["provenance"]
    assert "limit" not in data["arms"]["synthetic_arm_a"][1]["generations"][0]
    assert "procedure_initial" not in data["arms"]["synthetic_arm_a"][1]


def test_limit_noted_and_no_verdict(tmp_path):
    _, _, data = _run(tmp_path)
    assert any(
        "adjudicate_circuit_lineage.py" in text and "empreintes" in text
        for text in data["limits"]
    )
    assert set(data) == {"schema", "source", "provenance", "limits", "arms", "absent"}


def test_input_file_is_byte_identical_after_archiving(tmp_path):
    trace = _write_trace(tmp_path)
    before = trace.read_bytes()
    mod.archive(trace, tmp_path / "results" / "archive.json", root=tmp_path)
    assert trace.read_bytes() == before


def test_refuses_to_overwrite_existing_output(tmp_path):
    _, out, _ = _run(tmp_path)
    before = out.read_bytes()
    with pytest.raises(mod.ArchiveError):
        mod.archive(tmp_path / "synthetic_trace.json", out, root=tmp_path)
    assert out.read_bytes() == before


def test_refuses_output_outside_allowed_directories(tmp_path):
    trace = _write_trace(tmp_path)
    forbidden = [
        tmp_path / "other" / "a.json",
        tmp_path / "results" / ".." / "escape.json",
        tmp_path / "results_extra" / "a.json",
        tmp_path / "a.json",
    ]
    for target in forbidden:
        with pytest.raises(mod.ArchiveError):
            mod.archive(trace, target, root=tmp_path)
    assert not (tmp_path / "other").exists()
    assert not (tmp_path / "results_extra").exists()
    assert not (tmp_path / "escape.json").exists()
    assert not (tmp_path / "a.json").exists()
    assert mod.main([str(trace), str(tmp_path / "a.json")]) == 2
    assert not (tmp_path / "a.json").exists()


def test_experiment_directory_is_allowed(tmp_path):
    _, out, data = _run(tmp_path, folder="experiment")
    assert out.exists()
    assert data["schema"] == mod.SCHEMA


def test_refuses_symlinked_results_escaping_root(tmp_path):
    trace = _write_trace(tmp_path)
    repo = tmp_path / "repo"
    outside = tmp_path / "outside"
    repo.mkdir()
    outside.mkdir()
    try:
        (repo / "results").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("création de lien symbolique impossible")
    with pytest.raises(mod.ArchiveError):
        mod.archive(trace, repo / "results" / "a.json", root=repo)
    assert list(outside.iterdir()) == []


def test_plain_results_directory_is_accepted_and_written(tmp_path):
    trace = _write_trace(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    out = mod.archive(trace, repo / "results" / "a.json", root=repo)
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["schema"] == mod.SCHEMA


@pytest.mark.parametrize("name", ["results", "experiment"])
def test_refuses_symlink_to_other_repo_directory(tmp_path, name):
    trace = _write_trace(tmp_path)
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    try:
        (repo / name).symlink_to(docs, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("création de lien symbolique impossible")
    with pytest.raises(mod.ArchiveError):
        mod.archive(trace, repo / name / "a.json", root=repo)
    assert list(docs.iterdir()) == []
