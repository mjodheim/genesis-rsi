"""Read-only citation diagnostic; no diagnostic result is attested in advance.

This does not waive the historical failure 2860bfe9a13445beb3b42ccbe2b02c1d.
"""
from __future__ import annotations

import re

import check_repository_integrity as integrity

TARGETS = (
    "40ac0f64a1fb9465e1c4cadf6c32c0cfde3b84dd",
    "b8a8bb064ff456c491369bd1ca25c72ca187b545",
)
EXCLUDED = frozenset({
    "scripts/diagnose_citation_membership.py",
    "tests/test_diagnose_citation_membership.py",
})
FIELD = re.compile(
    r"""(?:"(?P<double>[^"\n]+)"|'(?P<single>[^'\n]+)'|"""
    r"""(?P<bare>[A-Za-z_][A-Za-z0-9_.-]*))\s*[:=]"""
)

def _field_before(line: str, offset: int) -> str | None:
    """Report the nearest lexical field on this line, without parsing the file."""
    candidates = list(FIELD.finditer(line, 0, offset))
    if not candidates:
        return None
    match = candidates[-1]
    return next(value for value in match.groups() if value is not None)

def main() -> int:
    collected = integrity.commit_typed_citations()
    print("Diagnostic en lecture seule ; aucune modification du manifeste.")
    print("None ne distingue pas un objet absent d'une erreur Git.")
    print("La chaîne vide '' est distincte de None.")
    print(f"COMMIT_FIELD = {integrity.COMMIT_FIELD.pattern!r}")
    print(f"COMMIT_FIELD flags = {integrity.COMMIT_FIELD.flags!r}")
    for sha in TARGETS:
        print(f"\nSHA {sha}")
        print(f"appartenance_collecte = {sha in collected!r}")
        print(f"collecte = {collected.get(sha)!r}")
        resolved = integrity._git("cat-file", "-e", sha + "^{commit}")
        print(f"_git('cat-file', '-e', {sha + '^{commit}'!r}) = {resolved!r}")

    tracked = integrity._git("ls-files", "-z")
    if tracked is None:
        raise RuntimeError("git ls-files a échoué ; occurrences non établies")
    counts = dict.fromkeys(TARGETS, 0)
    for relative in sorted(tracked.split("\0")):
        if not relative or relative in EXCLUDED:
            continue
        path = integrity.ROOT / relative
        if path.is_symlink() or not path.is_file():
            continue
        text = path.read_bytes().decode("utf-8", errors="surrogateescape")
        for number, line in enumerate(text.splitlines(), 1):
            for sha in TARGETS:
                for occurrence in re.finditer(re.escape(sha), line):
                    counts[sha] += 1
                    field = _field_before(line, occurrence.start())
                    search = (
                        integrity.COMMIT_FIELD.search(field)
                        if field is not None else None
                    )
                    exact = (
                        integrity.COMMIT_FIELD.fullmatch(field)
                        if field is not None else None
                    )
                    print(f"\noccurrence {sha} {relative!r}:{number}")
                    print(f"colonne = {occurrence.start() + 1}")
                    print(f"ligne = {line!r}")
                    print(f"champ_lexical = {field!r}")
                    print(
                        "COMMIT_FIELD.search(champ) = "
                        f"{search.group(0) if search is not None else None!r}"
                    )
                    print(f"COMMIT_FIELD.fullmatch(champ) = {exact is not None!r}")
                    if search is None:
                        print("OCCURRENCE SANS CHAMP RECONNU")
    for sha, count in counts.items():
        print(f"\noccurrences_fichiers_suivis[{sha}] = {count}")
    print(
        "Les champs lexicaux sont des indices locaux à une ligne ; "
        "l'appartenance est celle du collecteur appelé ci-dessus."
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
