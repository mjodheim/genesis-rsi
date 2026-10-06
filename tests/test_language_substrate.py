from pathlib import Path

from genesis.languages import substrate


def test_g1_inspects_all_initial_language_families_without_model_calls() -> None:
    samples = {
        "a.py": "def f(items):\n    return items[1]\n",
        "A.java": "class A { int f(int[] items) { return items[1]; } }\n",
        "A.cs": "class A { int F(int[] items) { return items[1]; } }\n",
        "a.rs": "fn f(items: &[i32]) -> i32 { items[1] }\n",
        "a.go": "package p\nfunc f(items []int) int { return items[1] }\n",
        "a.ts": "function f(items: number[]) { return items[1]; }\n",
    }

    languages = set()
    for path, source in samples.items():
        document = substrate.inspect_source(source, path=path)
        languages.add(document["language"])
        assert document["parse_ok"] is True
        assert document["external_model_calls"] == 0
        assert document["tokens"]
        assert any(node["kind"] == "subscript" for node in document["nodes"])
        assert document["document_digest"]

    assert languages == {"python", "java", "csharp", "rust", "go", "typescript"}


def test_python_uses_real_ast_and_exposes_symbols() -> None:
    source = "def add(value: int, delta: int):\n    result = value + delta\n    return result\n"
    document = substrate.inspect_source(source, path="math.py")

    assert document["structural_fidelity"] == "ast"
    assert document["parser_backend"].startswith("cpython_ast")
    assert {"function", "parameter", "variable"} <= {
        item["kind"] for item in document["symbols"]
    }
    assert any(item.get("name") == "add" for item in document["symbols"])


def test_documentation_requests_are_versioned_facts_not_network_fetches(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"dependencies":{"react":"19.1.0"},"devDependencies":{"vitest":"3.2.4"}}',
        encoding="utf-8",
    )
    (tmp_path / "a.ts").write_text("export const x = 1;\n", encoding="utf-8")

    project = substrate.inspect_project(tmp_path)
    requests = project["documentation_requests"]

    assert project["external_model_calls"] == 0
    assert project["languages"] == ["typescript"]
    assert {(item["package"], item["version"]) for item in requests} == {
        ("react", "19.1.0"),
        ("vitest", "3.2.4"),
    }
    assert all(item["network_fetched"] is False for item in requests)
