from pathlib import Path
from genesis import java_structural_mutations as jsm


def test_field_modifier_candidates_are_generic(tmp_path: Path) -> None:
    p = tmp_path / "src" / "A.java"
    p.parent.mkdir()
    p.write_text(
        "package p;\npublic class A {\n    private int count = 1;\n}\n",
        encoding="utf-8",
    )
    result = jsm.generate(tmp_path, include_prefixes=["src"], max_candidates=100)
    assert result["external_model_calls"] == 0
    assert any(
        c["operator"] == "java_field_modifier_add"
        and c["detail"]["modifier"] == "transient"
        for c in result["candidates"]
    )


def test_serialization_reinit_is_structure_derived(tmp_path: Path) -> None:
    p = tmp_path / "src" / "Cache.java"
    p.parent.mkdir()
    before = """package p;
import java.io.Serializable;
public class Cache implements Serializable {
    private Object cache;
    private int size;
    private void init() {
        cache = new Object();
        this.size = 3;
    }
}
"""
    p.write_text(before, encoding="utf-8")
    result = jsm.generate(tmp_path, include_prefixes=["src"], max_candidates=100)
    candidate = next(c for c in result["candidates"] if c["operator"] == "java_serialization_reinit")
    after = candidate["content_utf8"]
    assert "private transient Object cache;" in after
    assert "private transient int size;" in after
    assert "import java.io.ObjectInputStream;" in after
    assert "private void readObject(ObjectInputStream in)" in after
    assert "in.defaultReadObject();" in after
    assert "init();" in after


def test_scheduler_round_robins_across_java_files(tmp_path: Path) -> None:
    for name in ("A", "B", "C"):
        p = tmp_path / "src" / f"{name}.java"
        p.parent.mkdir(exist_ok=True)
        p.write_text(
            f"package p;\npublic class {name} {{\n    private int value = 1;\n}}\n",
            encoding="utf-8",
        )
    result = jsm.generate(tmp_path, include_prefixes=["src"], max_candidates=3)
    assert [c["path"] for c in result["candidates"]] == [
        "src/A.java", "src/B.java", "src/C.java"
    ]
