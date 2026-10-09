from pathlib import Path
import pytest

from genesis.repair_bench import Candidate, RepairBenchError, apply_transaction, run_arm, validate
from genesis.repair_lineage import Envelope, Ledger, lineage_proposer
from genesis.trust_root import digest_of
from test_repair_lineage import answer, genome, scripted, setup


def changes(path="src/B.java", search="old"):
    return [dict(path="src/A.java", edits=[dict(search="old", replace="new")]),
            dict(path=path, edits=[dict(search=search, replace="new")])]


def tree(root):
    (root / "src").mkdir(parents=True)
    (root / "test").mkdir()
    (root / "src/A.java").write_bytes(b"old\r\n")
    (root / "src/B.java").write_bytes(b"old\n")
    (root / "test/B.java").write_text("old")


class JointSandbox:
    def __init__(self, workspace, crash=False):
        self.workspace, self.crash, self.compiles = workspace, crash, 0

    def compile(self, directory):
        self.compiles += 1
        assert all((self.workspace / directory / "src" / name).read_text().strip() == "new"
                   for name in ("A.java", "B.java"))
        if self.crash:
            raise RuntimeError("interrupted validation")
        return type("Run", (), dict(ok=True, output=""))()

    def test(self, directory, **kwargs):
        return type("Run", (), dict(ok=True, output=""))()

    def failing_tests(self, directory):
        return []


@pytest.mark.parametrize("crash", [False, True])
def test_validation_sees_complete_transaction_and_restores_exact_bytes(tmp_path, crash):
    root = tmp_path / "case"
    tree(root)
    candidate = apply_transaction(root, changes(), "src", "test")
    sandbox = JointSandbox(tmp_path, crash)
    if crash:
        with pytest.raises(RuntimeError, match="interrupted"):
            validate(sandbox, "case", candidate, ["T::test"], source_directory="src")
    else:
        verdict = validate(sandbox, "case", candidate, ["T::test"], source_directory="src")
        assert verdict["plausible"] and verdict["paths"] == ["src/A.java", "src/B.java"]
    assert (root / "src/A.java").read_bytes() == b"old\r\n"
    assert (root / "src/B.java").read_bytes() == b"old\n"


@pytest.mark.parametrize("path,search", [("test/B.java", "old"), ("src/B.java", "absent"),
                                           ("src/A.java", "old"), ("src/../test/B.java", "old")])
def test_one_invalid_file_rejects_whole_transaction_without_mutation(tmp_path, path, search):
    tree(tmp_path)
    assert apply_transaction(tmp_path, changes(path, search), "src", "test") is None
    assert (tmp_path / "src/A.java").read_bytes() == b"old\r\n"


def test_transaction_limit_and_symlink_refusal(tmp_path):
    tree(tmp_path)
    assert apply_transaction(tmp_path, changes() * 2, "src", "test") is None
    assert apply_transaction(tmp_path, [], "src", "test") is None
    (tmp_path / "src/Link.java").symlink_to(tmp_path / "test/B.java")
    assert apply_transaction(tmp_path, changes("src/Link.java"), "src", "test") is None


def test_nested_test_directory_is_excluded_by_generator_and_validator(tmp_path):
    tree(tmp_path / "case")
    root = tmp_path / "case"
    (root / "src/test").mkdir()
    (root / "src/test/T.java").write_text("old")
    assert apply_transaction(root, changes("src/test/T.java"), "src", "t", test_directory="src/test") is None
    candidate = Candidate("src/A.java", "new", "t", extra_files=(("src/test/T.java", "new"),))
    with pytest.raises(RepairBenchError):
        validate(JointSandbox(tmp_path), "case", candidate, [], source_directory="src", test_directory="src/test")


def test_failure_writing_second_file_restores_first_and_does_not_compile(tmp_path, monkeypatch):
    tree(tmp_path / "case")
    candidate = apply_transaction(tmp_path / "case", changes(), "src", "t")
    sandbox = JointSandbox(tmp_path)
    original_write = Path.write_text
    def write(path, text, **kwargs):
        if path.name == "B.java":
            raise OSError("simulated write failure")
        return original_write(path, text, **kwargs)
    monkeypatch.setattr(Path, "write_text", write)
    with pytest.raises(OSError):
        validate(sandbox, "case", candidate, [], source_directory="src")
    assert sandbox.compiles == 0
    assert (tmp_path / "case/src/A.java").read_bytes() == b"old\r\n"
    assert (tmp_path / "case/src/B.java").read_bytes() == b"old\n"


def test_validator_rechecks_untrusted_multi_file_paths_before_writing(tmp_path):
    tree(tmp_path / "case")
    sandbox = JointSandbox(tmp_path)
    malicious = Candidate("src/A.java", "new", "t", extra_files=(("test/B.java", "new"),))
    with pytest.raises(RepairBenchError):
        validate(sandbox, "case", malicious, [], source_directory="src")
    assert (tmp_path / "case/src/A.java").read_bytes() == b"old\r\n"
    with pytest.raises(RepairBenchError):
        validate(sandbox, "case", malicious, [])


def test_digest_legacy_compatibility_and_transaction_order_independence(tmp_path):
    tree(tmp_path)
    assert Candidate("A.java", "x", "t").digest == digest_of(dict(path="A.java", content="x"))
    a = apply_transaction(tmp_path, changes(), "src", "t")
    b = apply_transaction(tmp_path, list(reversed(changes())), "src", "t")
    assert a.digest == b.digest


def test_arm_counts_whole_transaction_once_and_records_both_diffs(tmp_path):
    tree(tmp_path / "case")
    candidate = apply_transaction(tmp_path / "case", changes(), "src", "t")
    sandbox = JointSandbox(tmp_path)
    result = run_arm(sandbox, "case", dict(source_directory="src", failing_tests=["T::test"]),
                     lambda *args: [candidate], budget=1)
    assert result["solved"] and result["validated"] == sandbox.compiles == 1
    assert "a/src/A.java" in result["plausible_patch"] and "a/src/B.java" in result["plausible_patch"]


def test_model_can_submit_coordinated_repairs_and_legacy_shape_stays_unchanged(tmp_path):
    evidence = setup(tmp_path)
    (tmp_path / "src/B.java").write_text("class B { int n = 1; }")
    files = [dict(path="src/A.java", edits=[dict(search="return 1;", replace="return 0;")]),
             dict(path="src/B.java", edits=[dict(search="n = 1", replace="n = 0")])]
    send, seen = scripted(answer("submit_repairs", dict(candidates=[dict(hypothesis="coordinate", files=files)])))
    calls = []
    proposer = lineage_proposer(genome(), Envelope(model="test/model"), Ledger(1), calls,
                               transport=send, application_feedback=True, multi_file=True)
    candidates = proposer(tmp_path, evidence, (), 6)
    assert len(candidates) == 1 and len(candidates[0].files) == 2
    shape = seen[0]["tools"][0]["function"]["parameters"]["properties"]["candidates"]["items"]
    assert shape["required"] == ["hypothesis", "files"]
    assert calls[0]["submission_results"][0]["files"] == files
