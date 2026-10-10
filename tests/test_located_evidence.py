from genesis.located_evidence import located


def _evidence(tmp_path):
    source = tmp_path / "src" / "A.java"
    source.parent.mkdir()
    source.write_text("\n".join(f"line {index}" for index in range(1, 301)), encoding="utf-8")
    return {"source_directory": "src", "test_directory": "test", "failing_tests": ["T::t"],
            "suspect_locations": [["src/A.java", 5]], "production_source": [], "evidence_digest": "old"}


def test_the_excerpts_follow_the_given_locations(tmp_path):
    evidence = located(_evidence(tmp_path), tmp_path, [["src/A.java", 200], ["src/Missing.java", 3], ["x/B.java", 1]],
                       "program")
    assert evidence["suspect_locations"] == [["src/A.java", 200]]
    assert [(item["path"], item["first_line"] <= 200 <= item["last_line"]) for item in evidence["production_source"]] \
        == [("src/A.java", True)]
    assert evidence["localization"] == {"origin": "program", "locations": 1, "fallback": False}
    assert evidence["evidence_digest"] != "old" and evidence["failing_tests"] == ["T::t"]


def test_without_a_usable_location_the_collected_evidence_is_kept(tmp_path):
    evidence = located(_evidence(tmp_path), tmp_path, [["src/Missing.java", 3]], "program")
    assert evidence["suspect_locations"] == [["src/A.java", 5]] and evidence["localization"]["fallback"]
