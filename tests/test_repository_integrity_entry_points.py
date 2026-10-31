"""Entry points recognised by the repository integrity orphan check.

Every tree below is a synthetic fixture built in a temporary directory; nothing here
touches the network or the real scientific record.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

CHECKER_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "check_repository_integrity.py"
)

# Synthetic fixture content: a module with no imports.
SYNTHETIC_SOURCE = '"""Synthetic fixture."""\n'


def _load_checker():
    spec = importlib.util.spec_from_file_location("_integrity_under_test", CHECKER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def checker():
    return _load_checker()


@pytest.fixture
def synthetic_tree(tmp_path, checker, monkeypatch):
    """Synthetic fixture tree: one listed entry point and one unlisted neighbour."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "archive_circuit_lineage_evidence.py").write_text(
        SYNTHETIC_SOURCE, encoding="utf-8"
    )
    (scripts / "archive_other.py").write_text(SYNTHETIC_SOURCE, encoding="utf-8")
    (scripts / "locate_circuit2_launcher_revision.py").write_text(
        SYNTHETIC_SOURCE, encoding="utf-8"
    )
    (scripts / "locate_circuit2_other.py").write_text(SYNTHETIC_SOURCE, encoding="utf-8")
    (scripts / "export_circuit2_launcher_revision.py").write_text(
        SYNTHETIC_SOURCE, encoding="utf-8"
    )
    (scripts / "export_circuit2_other.py").write_text(SYNTHETIC_SOURCE, encoding="utf-8")
    monkeypatch.setattr(checker, "ROOT", tmp_path)
    monkeypatch.setattr(checker, "PACKAGES", ("genesis",))
    return tmp_path


def test_listed_entry_point_is_not_reported(checker, synthetic_tree):
    problems = checker.check_orphans()
    assert not any("archive_circuit_lineage_evidence.py" in p for p in problems)
    assert not any("locate_circuit2_launcher_revision.py" in p for p in problems)
    assert not any("export_circuit2_launcher_revision.py" in p for p in problems)


def test_unlisted_neighbour_is_still_reported(checker, synthetic_tree):
    problems = checker.check_orphans()
    assert problems == [
        "scripts/archive_other.py is not imported by any entry point",
        "scripts/export_circuit2_other.py is not imported by any entry point",
        "scripts/locate_circuit2_other.py is not imported by any entry point",
    ]


def test_entry_point_constants_are_exact(checker):
    assert checker.ENTRY_POINT_NAMES == {
        "archive_circuit_lineage_evidence",
        "locate_circuit2_launcher_revision",
        "export_circuit2_launcher_revision",
    }
    assert checker.ENTRY_POINT_PREFIXES == (
        "run_", "audit_", "author_", "build_", "train_", "check_",
        "g11_", "g12_", "select_", "preregister_",
    )


def test_real_repository_has_no_orphan(checker):
    assert checker.check_orphans() == []
