import json
from pathlib import Path

from genesis import localized_evidence
from genesis.trust_root import digest_of

MODULE = "def localize(case):\n    return []\n"


def _checkout(tmp_path: Path) -> tuple[Path, dict]:
    root = tmp_path / "P-1-b"
    (root / "src/p").mkdir(parents=True)
    (root / "test/p").mkdir(parents=True)
    (root / "src/p/Thing.java").write_text("\n".join(f"line {n}" for n in range(1, 200)), encoding="utf-8")
    (root / "src/p/Other.java").write_text("\n".join(f"other {n}" for n in range(1, 200)), encoding="utf-8")
    (root / "src/p/notes.txt").write_text("not java", encoding="utf-8")
    (root / "test/p/ThingTest.java").write_text("test", encoding="utf-8")
    (root / "failing_tests").write_text(
        "--- p.ThingTest::testIt\nError\n\tat p.Thing.run(Thing.java:30)\n"
        "--- p.NetworkTest::needsNetwork\nUnknownHostException\n", encoding="utf-8")
    body = {"source_directory": "src", "test_directory": "test", "failing_tests": ["p.ThingTest::testIt"],
            "traces": [], "suspect_locations": [["src/p/Thing.java", 30]], "suspects_from_stack_trace": False,
            "test_source": [], "production_source": [{"path": "src/p/Thing.java"}]}
    return root, {**body, "evidence_digest": digest_of(body)}


def _runner(locations, seen):
    def run(command, **_):
        out = Path(next(part for part in command if part.endswith("target=/out")).split("source=")[1].split(",")[0])
        cases = Path(next(part for part in command if "target=/cases" in part).split("source=")[1].split(",")[0])
        seen["case"] = json.loads((cases / "case/case.json").read_text())
        seen["files"] = sorted(str(path.relative_to(cases)) for path in cases.rglob("*") if path.is_file())
        (out / "result.json").write_text(json.dumps({"case": {"locations": locations}}))
    return run


def test_report_keeps_only_the_named_failing_tests(tmp_path):
    root, evidence = _checkout(tmp_path)
    report = localized_evidence.trigger_report(root, evidence["failing_tests"])
    assert "Thing.java:30" in report and "NetworkTest" not in report


def test_module_locations_replace_suspects_and_excerpts(tmp_path):
    root, evidence = _checkout(tmp_path)
    seen: dict = {}
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    answer = [["src/p/Other.java", 100], ["test/p/ThingTest.java", 1], ["src/p/Missing.java", 4], ["../x.java", 1]]
    changed = localized_evidence.relocalize(evidence, root, MODULE, image="i", scratch=scratch, runner=_runner(answer, seen))
    assert changed["suspect_locations"] == [["src/p/Other.java", 100]] and changed["suspects_from_stack_trace"]
    assert changed["production_source"][0]["first_line"] == 60 and changed["production_source"][0]["last_line"] == 140
    assert changed["localization"] == {"module_sha256": changed["localization"]["module_sha256"], "locations": 1,
                                       "error": None, "fallback": False}
    assert changed["evidence_digest"] != evidence["evidence_digest"]
    assert changed["failing_tests"] == evidence["failing_tests"]
    assert seen["case"]["report"].startswith("--- p.ThingTest::testIt") and "NetworkTest" not in seen["case"]["report"]
    assert seen["files"] == ["case/case.json", "case/tree/src/p/Other.java", "case/tree/src/p/Thing.java",
                             "case/tree/test/p/ThingTest.java"]
    assert list(scratch.iterdir()) == []


def test_no_usable_location_keeps_the_collected_evidence(tmp_path):
    root, evidence = _checkout(tmp_path)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    kept = localized_evidence.relocalize(evidence, root, MODULE, image="i", scratch=scratch, runner=_runner([], {}))
    assert kept["suspect_locations"] == evidence["suspect_locations"] and not kept["suspects_from_stack_trace"]
    assert kept["production_source"] == evidence["production_source"] and kept["localization"]["fallback"]
