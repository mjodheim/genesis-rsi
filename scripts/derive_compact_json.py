#!/usr/bin/env python3
"""Dérivation JSON compacte vérifiée (dérivé de présentation).

Lit les octets exacts d'un JSON source, en calcule le SHA-256 sans jamais
réserialiser, écrit une version compacte déterministe et un manifeste.
Aucune expérience n'est relancée ; aucun réseau, aucun modèle.
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

MENTION = "dérivé de présentation, aucune preuve expérimentale ajoutée"
_COMMIT_RE = re.compile(r"[0-9a-fA-F]{40}")


class DerivationError(ValueError):
    """Erreur de dérivation : aucune sortie n'est produite."""


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def _reject_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DerivationError(f"clé dupliquée : {key!r}")
        result[key] = value
    return result


def _reject_constant(name):
    raise DerivationError(f"constante JSON non finie refusée : {name}")


def load_strict(data):
    """Charge des octets UTF-8 en JSON en refusant les clés dupliquées."""
    try:
        return json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_reject_duplicates,
            parse_constant=_reject_constant,
        )
    except DerivationError:
        raise
    except ValueError as exc:
        raise DerivationError(f"JSON invalide : {exc}") from exc


def compact_bytes(value):
    """Sérialisation compacte déterministe, UTF-8, un seul saut de ligne final."""
    text = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    try:
        return (text + "\n").encode("utf-8")
    except UnicodeEncodeError as exc:
        raise DerivationError(f"encodage UTF-8 impossible : {exc}") from exc


def strict_equal(a, b):
    """Égalité récursive stricte : types ET valeurs (1, True, 1.0 distincts)."""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        if a.keys() != b.keys():
            return False
        return all(strict_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(strict_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, float):
        return a == b and repr(a) == repr(b)
    return a == b


def _check_commit(commit):
    if not isinstance(commit, str) or _COMMIT_RE.fullmatch(commit) is None:
        raise DerivationError("commit source : 40 caractères hexadécimaux exigés")
    return commit.lower()


def _check_output(path, root):
    p = Path(path)
    resolved = p.resolve()
    root_resolved = Path(root).resolve()
    if resolved == root_resolved or not resolved.is_relative_to(root_resolved):
        raise DerivationError(f"sortie hors de {root} : {path}")
    if p.is_symlink() or resolved.exists():
        raise DerivationError(f"refus d'écraser : {path}")
    return resolved


def derive(
    source,
    compact_out,
    manifest_out,
    repo,
    source_commit,
    original_path,
    results_root="results",
):
    """Produit le fichier compact et le manifeste ; retourne le manifeste."""
    commit = _check_commit(source_commit)
    if not isinstance(repo, str) or not repo.strip():
        raise DerivationError("dépôt manquant")
    if not isinstance(original_path, str) or not original_path.strip():
        raise DerivationError("chemin original manquant")
    compact_path = _check_output(compact_out, results_root)
    manifest_path = _check_output(manifest_out, results_root)
    if compact_path == manifest_path:
        raise DerivationError("les deux sorties sont identiques")

    original = Path(source).read_bytes()
    value = load_strict(original)
    compact = compact_bytes(value)
    if not strict_equal(value, load_strict(compact)):
        raise DerivationError("la version compacte diffère de la source")
    compact_sha = sha256_hex(compact)

    manifest = {
        "depot": repo,
        "commit_source": commit,
        "chemin_original": original_path,
        "sha256_octets_originaux": sha256_hex(original),
        "sha256_fichier_compact": compact_sha,
        "mention": MENTION,
    }
    manifest_data = (
        json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")

    compact_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(compact_path, "xb") as fh:
        fh.write(compact)
    try:
        with open(manifest_path, "xb") as fh:
            fh.write(manifest_data)
        if sha256_hex(compact_path.read_bytes()) != compact_sha:
            raise DerivationError("relecture du fichier compact incohérente")
    except BaseException:
        compact_path.unlink()
        raise
    return manifest


def build_parser():
    parser = argparse.ArgumentParser(
        description="Dérive un JSON compact vérifié et son manifeste (sous results/)."
    )
    parser.add_argument("source", help="fichier JSON source (octets lus tels quels)")
    parser.add_argument("compact_out", help="sortie compacte sous results/")
    parser.add_argument("manifest_out", help="sortie du manifeste sous results/")
    parser.add_argument("repo", help="dépôt d'origine")
    parser.add_argument("source_commit", help="commit source complet (40 hex)")
    parser.add_argument("original_path", help="chemin original dans ce commit")
    parser.add_argument("--results-root", default="results", help=argparse.SUPPRESS)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        manifest = derive(
            args.source,
            args.compact_out,
            args.manifest_out,
            args.repo,
            args.source_commit,
            args.original_path,
            results_root=args.results_root,
        )
    except (ValueError, OSError) as exc:
        print(f"erreur : {exc}", file=sys.stderr)
        return 1
    print(f"sha256 source  : {manifest['sha256_octets_originaux']}")
    print(f"sha256 compact : {manifest['sha256_fichier_compact']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
