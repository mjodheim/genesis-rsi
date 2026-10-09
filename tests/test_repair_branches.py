import pytest

from genesis.repair_bench import Candidate, run_arm
from genesis.repair_branches import archive_prompt, extend_branch, find_parent, read_branch
from genesis.repair_lineage import Envelope, GenomeError, Ledger, lineage_proposer
from test_repair_lineage import answer, genome, scripted, setup
from test_repair_transactions import JointSandbox, tree


def history(parent):
    return [(parent, dict(candidate_digest=parent.digest, stopped_at="failing_tests"))]


def edits(path, old, new):
    return [dict(path=path, edits=[dict(search=old, replace=new)])]


def test_virtual_inspection_and_extension_preserve_parent_changes_without_writes(tmp_path):
    evidence = setup(tmp_path)
    parent = Candidate("src/A.java", "class A { int n = 7; }", "test")
    h = history(parent)
    viewed = read_branch(tmp_path, evidence, h, dict(path="src/A.java", branch=parent.digest))
    assert "n = 7" in viewed and "return 1;" in (tmp_path / "src/A.java").read_text()
    child = extend_branch(tmp_path, evidence, parent, edits("src/A.java", "n = 7", "n = 8"), "t", "extend")
    assert "n = 8" in child.content and child.provenance["branch_parent_digest"] == parent.digest
    assert "return 1;" in (tmp_path / "src/A.java").read_text()
    next_child = extend_branch(tmp_path, evidence, child, edits("src/A.java", "n = 8", "n = 9"), "t", "again")
    assert next_child.provenance["branch_depth"] == 2


def test_extension_adds_second_file_and_complete_child_is_validated_once(tmp_path):
    tree(tmp_path / "case")
    root = tmp_path / "case"
    evidence = dict(source_directory="src", test_directory="test", failing_tests=["T::test"])
    parent = Candidate("src/A.java", "new\n", "t")
    child = extend_branch(root, evidence, parent, edits("src/B.java", "old", "new"), "t", "joint")
    assert len(child.files) == 2
    sandbox = JointSandbox(tmp_path)
    outcome = run_arm(sandbox, "case", evidence, lambda *args: [child], 1)
    assert outcome["solved"] and outcome["validated"] == 1
    assert "a/src/A.java" in outcome["plausible_patch"] and "a/src/B.java" in outcome["plausible_patch"]
    assert (root / "src/A.java").read_bytes() == b"old\r\n"


def test_unknown_or_ungraded_branch_is_refused(tmp_path):
    evidence = setup(tmp_path)
    parent = Candidate("src/A.java", "new", "t")
    assert find_parent([], parent.digest) is None
    assert find_parent([(parent, dict(candidate_digest="wrong"))], parent.digest) is None
    with pytest.raises(ValueError, match="unknown"):
        read_branch(tmp_path, evidence, [], dict(path="src/A.java", branch=parent.digest))


def test_extension_cannot_edit_tests_or_grow_beyond_three_files(tmp_path):
    tree(tmp_path)
    evidence = dict(source_directory="src", test_directory="test")
    for name in ("C", "D"):
        (tmp_path / f"src/{name}.java").write_text("old")
    parent = Candidate("src/A.java", "new", "t", extra_files=(("src/B.java", "new"), ("src/C.java", "new")))
    assert extend_branch(tmp_path, evidence, parent, edits("src/D.java", "old", "new"), "t", "too large") is None
    assert extend_branch(tmp_path, evidence, parent, edits("test/B.java", "old", "new"), "t", "test") is None
    child = extend_branch(tmp_path, evidence, parent, edits("src/C.java", "new", "old"), "t", "revert")
    assert len(child.files) == 2 and "src/C.java" not in dict(child.files)


def test_model_can_read_and_extend_graded_candidate_within_same_request_budget(tmp_path):
    evidence = setup(tmp_path)
    parent = Candidate("src/A.java", "class A { int n = 7; }", "t")
    send, seen = scripted(answer("read_file", dict(path="src/A.java", branch=parent.digest)),
        answer("submit_repairs", dict(candidates=[dict(hypothesis="extend", parent=parent.digest,
                                                      files=edits("src/A.java", "n = 7", "n = 8"))])))
    calls = []
    proposer = lineage_proposer(genome(inspection_requests=1, rounds=1), Envelope(model="test/model"), Ledger(1),
                               calls, transport=send, application_feedback=True, multi_file=True, branching=True)
    candidates = proposer(tmp_path, evidence, history(parent), 6)
    assert len(candidates) == 1 and "n = 8" in candidates[0].content
    assert "n = 7" in seen[1]["messages"][-2]["content"]
    assert parent.digest in archive_prompt(history(parent))
    assert calls[-1]["submission_results"][0]["parent"] == parent.digest
    assert calls[-1]["submission_results"][0]["branch_depth"] == 1
    assert len(calls) == 2


def test_branch_mode_requires_multi_file_mode():
    with pytest.raises(GenomeError, match="require"):
        lineage_proposer(genome(), Envelope(model="test/model"), Ledger(1), [], branching=True)
