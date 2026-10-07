from pathlib import Path

from genesis import java_range_mutations as jrm


def test_derives_upper_bound_from_optional_array_domain(tmp_path: Path) -> None:
    p = tmp_path / "src" / "Generator.java"
    p.parent.mkdir()
    p.write_text(
        """class Generator {
    char choose(int start, int end, char[] pool) {
        if (start == 0 && end == 0) {
            end = 128;
            start = 32;
        }
        int gap = end - start;
        if (pool == null) {
            return 'x';
        }
        return pool[start];
    }
}
""",
        encoding="utf-8",
    )
    result = jrm.generate(tmp_path, include_prefixes=["src"], max_candidates=100)
    assert any(
        "if (pool != null)" in c["content_utf8"]
        and "end = pool.length;" in c["content_utf8"]
        for c in result["candidates"]
    )


def test_requires_zero_zero_sentinel_and_local_array_evidence(tmp_path: Path) -> None:
    p = tmp_path / "src" / "Generator.java"
    p.parent.mkdir()
    p.write_text(
        """class Generator {
    char choose(int start, int end, char[] pool) {
        int gap = end - start;
        return pool[start];
    }
}
""",
        encoding="utf-8",
    )
    result = jrm.generate(tmp_path, include_prefixes=["src"], max_candidates=100)
    assert result["candidate_count"] == 0


def test_requires_gap_semantics_for_same_bounds(tmp_path: Path) -> None:
    p = tmp_path / "src" / "Generator.java"
    p.parent.mkdir()
    p.write_text(
        """class Generator {
    char choose(int start, int end, char[] pool) {
        if (start == 0 && end == 0) {
            end = 10;
        }
        if (pool == null) {
            return 'x';
        }
        return pool[start];
    }
}
""",
        encoding="utf-8",
    )
    result = jrm.generate(tmp_path, include_prefixes=["src"], max_candidates=100)
    assert result["candidate_count"] == 0


def test_round_robin_across_files(tmp_path: Path) -> None:
    for name in ("A", "B"):
        p = tmp_path / "src" / f"{name}.java"
        p.parent.mkdir(exist_ok=True)
        p.write_text(
            f"""class {name} {{
    char f(int lo, int hi, char[] values) {{
        if (lo == 0 && hi == 0) {{
            hi = 20;
        }}
        int gap = hi - lo;
        if (values == null) return 'x';
        return values[lo];
    }}
}}
""",
            encoding="utf-8",
        )
    result = jrm.generate(tmp_path, include_prefixes=["src"], max_candidates=2)
    assert [c["path"] for c in result["candidates"]] == ["src/A.java", "src/B.java"]
