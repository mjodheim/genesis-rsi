#!/usr/bin/env python3
"""Découpage et réassemblage vérifiable du résultat CIRCUIT2 complet.

Le fichier source n'est jamais modifié : il est seulement lu. Le découpage est
purement structurel (par bras, puis par groupes de graines consécutives) ;
aucune valeur n'est calculée, convertie ou interprétée, aucun gain ni succès
n'est évalué. Aucun accès réseau, aucun modèle. Écriture uniquement sous
results/, en mode exclusif ('x') : aucun fichier existant n'est écrasé.

Sous-commandes :
  split  SOURCE OUT_DIR [--seeds-per-shard N] [--max-fragment-chars N]
  verify MANIFEST [--source CHEMIN]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HEADER_KEYS = ("plan_digest", "machinery_commit", "seeds", "generations", "scale")
ARMS_KEY = "arms"
FRAGMENT_EXTRA_KEYS = ("arm", "seed_index_range", "runs")
MANIFEST_NAME = "MANIFEST.json"
MANIFEST_VERSION = 1
DEFAULT_SEEDS_PER_SHARD = 5
DEFAULT_MAX_FRAGMENT_CHARS = 100_000
DEFAULT_RESULTS_ROOT = "results"
MANIFEST_KEYS = (
    "manifest_version",
    "source_name",
    "source_sha256",
    "source_bytes",
    "seeds_per_shard",
    "top_level_keys",
    "arms_order",
    "fragment_count",
    "reassembly_order",
    "fragments",
)
ENTRY_KEYS = ("order", "file", "sha256", "bytes", "arm", "seed_index_range")


class ShardError(Exception):
    """Refus explicite : entrée, fragment ou manifeste non conforme."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _dump(obj) -> str:
    """Sérialisation canonique du résultat : json.dumps(indent=2) + newline."""
    return json.dumps(obj, indent=2) + "\n"


def _positive_int(value, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ShardError(f"{label} doit être un entier >= 1 (reçu : {value!r})")
    return value


def _resolve_output_dir(out_dir, results_root) -> Path:
    root = Path(DEFAULT_RESULTS_ROOT if results_root is None else results_root).resolve()
    out = Path(out_dir).resolve()
    try:
        out.relative_to(root)
    except ValueError:
        raise ShardError(f"écriture refusée hors de {root} : {out}") from None
    return out


def _safe_part(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", text)[:60]


def split(
    source,
    out_dir,
    seeds_per_shard: int = DEFAULT_SEEDS_PER_SHARD,
    max_fragment_chars: int = DEFAULT_MAX_FRAGMENT_CHARS,
    results_root=None,
) -> Path:
    """Découpe `source` en fragments sous `out_dir` ; retourne le chemin du manifeste."""
    _positive_int(seeds_per_shard, "seeds_per_shard")
    _positive_int(max_fragment_chars, "max_fragment_chars")
    out = _resolve_output_dir(out_dir, results_root)
    source = Path(source)
    raw = source.read_bytes()
    try:
        obj = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ShardError(f"source illisible : {exc}") from exc
    if _dump(obj).encode("utf-8") != raw:
        raise ShardError(
            "la source n'est pas exactement json.dumps(objet, indent=2) + newline : "
            "réassemblage exact impossible, découpage refusé"
        )
    if not isinstance(obj, dict) or set(obj) != set(HEADER_KEYS) | {ARMS_KEY}:
        raise ShardError("structure de source inattendue (clés de premier niveau)")
    arms = obj[ARMS_KEY]
    if not isinstance(arms, dict) or not arms:
        raise ShardError("'arms' doit être un objet non vide")
    header = {key: obj[key] for key in HEADER_KEYS}
    planned = []
    entries = []
    for arm, runs in arms.items():
        if not isinstance(runs, list):
            raise ShardError(f"le bras {arm!r} n'est pas une liste d'exécutions")
        starts = list(range(0, len(runs), seeds_per_shard)) or [0]
        for start in starts:
            stop = min(start + seeds_per_shard, len(runs))
            fragment = dict(header)
            fragment["arm"] = arm
            fragment["seed_index_range"] = [start, stop]
            fragment["runs"] = runs[start:stop]
            text = _dump(fragment)
            if len(text) > max_fragment_chars:
                raise ShardError(
                    f"fragment trop grand ({len(text)} > {max_fragment_chars} caractères) : "
                    f"bras {arm!r}, graines [{start}, {stop})"
                )
            data = text.encode("utf-8")
            index = len(entries)
            name = f"{index:04d}_{_safe_part(arm)}_{start}-{stop}.json"
            planned.append((name, data))
            entries.append(
                {
                    "order": index,
                    "file": name,
                    "sha256": _sha256(data),
                    "bytes": len(data),
                    "arm": arm,
                    "seed_index_range": [start, stop],
                }
            )
    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "source_name": source.name,
        "source_sha256": _sha256(raw),
        "source_bytes": len(raw),
        "seeds_per_shard": seeds_per_shard,
        "top_level_keys": list(obj),
        "arms_order": list(arms),
        "fragment_count": len(entries),
        "reassembly_order": [entry["file"] for entry in entries],
        "fragments": entries,
    }
    planned.append((MANIFEST_NAME, _dump(manifest).encode("utf-8")))
    for name, _ in planned:
        target = out / name
        if target.exists() or target.is_symlink():
            raise ShardError(f"refus d'écrasement : {target} existe déjà")
    out.mkdir(parents=True, exist_ok=True)
    for name, data in planned:
        with open(out / name, "xb") as handle:
            handle.write(data)
    return out / MANIFEST_NAME


def _read_manifest(path: Path) -> dict:
    try:
        manifest = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise ShardError(f"manifeste illisible : {exc}") from exc
    if not isinstance(manifest, dict) or set(manifest) != set(MANIFEST_KEYS):
        raise ShardError("manifeste invalide : clés manquantes ou inattendues")
    if manifest["manifest_version"] != MANIFEST_VERSION:
        raise ShardError("version de manifeste non prise en charge")
    entries = manifest["fragments"]
    if not isinstance(entries, list) or not entries:
        raise ShardError("manifeste invalide : liste de fragments absente ou vide")
    if manifest["fragment_count"] != len(entries):
        raise ShardError(
            f"nombre de fragments modifié : {manifest['fragment_count']} annoncés, "
            f"{len(entries)} listés"
        )
    for position, entry in enumerate(entries):
        if not isinstance(entry, dict) or set(entry) != set(ENTRY_KEYS):
            raise ShardError(f"entrée de fragment invalide à la position {position}")
        if entry["order"] != position:
            raise ShardError(
                f"ordre des fragments modifié à la position {position} "
                f"(order={entry['order']!r})"
            )
        name = entry["file"]
        if not isinstance(name, str) or name in ("", ".", "..") or name != Path(name).name:
            raise ShardError(f"nom de fragment invalide : {name!r}")
    if manifest["reassembly_order"] != [entry["file"] for entry in entries]:
        raise ShardError("ordre de réassemblage incohérent avec la liste des fragments")
    keys = manifest["top_level_keys"]
    if not isinstance(keys, list) or sorted(map(str, keys)) != sorted((*HEADER_KEYS, ARMS_KEY)):
        raise ShardError("manifeste invalide : top_level_keys")
    return manifest


def _read_fragment_bytes(base: Path, entry: dict) -> bytes:
    path = base / entry["file"]
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ShardError(f"fragment illisible {entry['file']} : {exc}") from exc
    if len(data) != entry["bytes"] or _sha256(data) != entry["sha256"]:
        raise ShardError(
            f"empreinte non conforme pour {entry['file']} : fragment altéré"
        )
    return data


def _parse_range(value, label: str):
    ok = (
        isinstance(value, list)
        and len(value) == 2
        and all(isinstance(v, int) and not isinstance(v, bool) for v in value)
        and 0 <= value[0] <= value[1]
    )
    if not ok:
        raise ShardError(f"plage de graines invalide pour {label} : {value!r}")
    return value[0], value[1]


def _refuse_unlisted(path: Path, entries: list) -> None:
    """Refuse tout fichier ou sous-dossier du dossier du manifeste non listé."""
    allowed = {MANIFEST_NAME, path.name} | {entry["file"] for entry in entries}
    try:
        present = sorted(item.name for item in path.parent.iterdir())
    except OSError as exc:
        raise ShardError(f"dossier du manifeste illisible : {exc}") from exc
    unlisted = [name for name in present if name not in allowed]
    if unlisted:
        raise ShardError(
            "élément non listé dans le manifeste (fichier ou sous-dossier en trop) : "
            + ", ".join(repr(name) for name in unlisted)
        )


def reassemble(manifest_path, source=None) -> bytes:
    """Vérifie le dossier et les empreintes puis reconstruit les octets exacts de la source.

    Si `source` est fourni, les octets reconstruits sont comparés à ceux de ce
    fichier (lecture seule) ; toute différence est refusée.
    """
    path = Path(manifest_path)
    manifest = _read_manifest(path)
    entries = manifest["fragments"]
    _refuse_unlisted(path, entries)
    payloads = [_read_fragment_bytes(path.parent, entry) for entry in entries]
    expected_keys = set(HEADER_KEYS) | set(FRAGMENT_EXTRA_KEYS)
    header = None
    arms: dict = {}
    last_arm = None
    for entry, data in zip(entries, payloads):
        label = entry["file"]
        try:
            fragment = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ShardError(f"fragment {label} : JSON invalide ({exc})") from exc
        if not isinstance(fragment, dict) or set(fragment) != expected_keys:
            raise ShardError(f"fragment {label} : clés inattendues")
        arm = fragment["arm"]
        if not isinstance(arm, str) or arm != entry["arm"]:
            raise ShardError(f"fragment {label} : bras différent du manifeste")
        start, stop = _parse_range(fragment["seed_index_range"], label)
        if _dump(fragment["seed_index_range"]) != _dump(entry["seed_index_range"]):
            raise ShardError(f"fragment {label} : plage différente du manifeste")
        runs = fragment["runs"]
        if not isinstance(runs, list) or len(runs) != stop - start:
            raise ShardError(f"fragment {label} : exécutions incohérentes avec la plage")
        current = _dump({key: fragment[key] for key in HEADER_KEYS})
        if header is None:
            header = {key: fragment[key] for key in HEADER_KEYS}
        elif current != _dump(header):
            raise ShardError(f"fragment {label} : en-tête différent des autres fragments")
        if arm not in arms:
            arms[arm] = []
        elif arm != last_arm:
            raise ShardError(f"fragment {label} : fragments du bras {arm!r} non contigus")
        if start != len(arms[arm]):
            raise ShardError(f"fragment {label} : graines non consécutives")
        arms[arm].extend(runs)
        last_arm = arm
    if list(arms) != manifest["arms_order"]:
        raise ShardError("ordre des bras différent du manifeste")
    parts = {**header, ARMS_KEY: arms}
    obj = {key: parts[key] for key in manifest["top_level_keys"]}
    data = _dump(obj).encode("utf-8")
    if len(data) != manifest["source_bytes"] or _sha256(data) != manifest["source_sha256"]:
        raise ShardError(
            "reconstruction refusée : le sha256 obtenu ne correspond pas à celui "
            "du fichier source"
        )
    if source is not None:
        try:
            reference = Path(source).read_bytes()
        except OSError as exc:
            raise ShardError(f"source illisible : {exc}") from exc
        if data != reference:
            raise ShardError(
                "reconstruction refusée : les octets reconstruits diffèrent "
                f"du fichier source fourni ({source})"
            )
    return data


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shard_circuit2_result",
        description="Découpe et vérifie le résultat CIRCUIT2 complet (lecture seule sur la source).",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    p_split = sub.add_parser("split", help="découpe la source en fragments sous results/")
    p_split.add_argument("source")
    p_split.add_argument("out_dir")
    p_split.add_argument("--seeds-per-shard", type=int, default=DEFAULT_SEEDS_PER_SHARD)
    p_split.add_argument("--max-fragment-chars", type=int, default=DEFAULT_MAX_FRAGMENT_CHARS)
    p_verify = sub.add_parser("verify", help="vérifie les empreintes et la reconstruction")
    p_verify.add_argument("manifest")
    p_verify.add_argument("--source", default=None, help="fichier source à comparer aux octets reconstruits (lecture seule)")
    return parser


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "split":
            manifest = split(
                args.source,
                args.out_dir,
                seeds_per_shard=args.seeds_per_shard,
                max_fragment_chars=args.max_fragment_chars,
            )
            print(f"Manifeste écrit : {manifest}")
        else:
            data = reassemble(args.manifest, source=args.source)
            if args.source is None:
                print(f"OK : reconstruction conforme au manifeste ({len(data)} octets, sha256={_sha256(data)}) ; source non comparée")
            else:
                print(f"OK : reconstruction identique au fichier source {args.source} ({len(data)} octets, sha256={_sha256(data)})")
    except (ShardError, OSError) as exc:
        print(f"REFUS : {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
