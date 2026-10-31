"""Lanceur CIRCUIT2 ancré : vérifie l'empreinte SHA-256 du sceau approuvé avant toute génération.

Ce script n'est pas scellé. Le lanceur scellé (run_circuit2_campaign.py) est appelé
inchangé, mais plus importé au niveau du module : il n'est chargé qu'une fois les
contrôles passés. Avant tout import du code candidat, le script lit en octets et hache le
lanceur, le vérificateur seal_circuit2_launcher.py et le sceau, puis compare ces empreintes
à celles du fichier d'approbation hôte. L'empreinte approuvée n'est jamais lue sur la ligne
de commande : elle vient de ce fichier, dont le chemin est donné par la variable
d'environnement GENESIS_HOST_APPROVALS (JSON avec les clés circuit2_launcher_seal_sha256,
circuit2_launcher_sha256, circuit2_verifier_sha256, empreintes de 64 hex minuscules, et
circuit2_launcher_seal_path, chemin du sceau approuvé).
Tout ce qui vit dans le dépôt pouvant être modifié conjointement par un candidat, ce
fichier doit se trouver hors de la racine du dépôt, n'être inscriptible ni par le groupe ni
par les autres, et appartenir à root ou à un autre uid que l'uid courant. L'indépendance de
l'approbation dépend de la configuration de l'hôte ; le dépôt ne la prouve pas. Sous root,
un fichier appartenant à root est accepté par cette règle. Il en va de même de chaque
répertoire ancêtre du fichier (jusqu'à /) : ni inscriptible par le groupe ou les autres,
sauf s'il porte le bit sticky et appartient à root, ni possédé par l'uid courant (non
root), faute de quoi le fichier pourrait être remplacé par renommage. Le lanceur et le
vérificateur sont lus en octets une seule fois, dans check_approved : ces mêmes octets
sont hachés puis exécutés (compile et exec) dans des modules créés à la main, sans
cache de bytecode (sys.dont_write_bytecode) ; un .pyc de __pycache__ n'est jamais utilisé
pour eux. Limite : les autres modules importés par le lanceur restent chargés par
l'import ordinaire ; ils ne sont couverts ni par ces empreintes ni par cette protection.
Refus (code 2) avant toute génération et avant tout import du module de campagne, sans
sortie standard et sans fichier --out, si la variable est absente, si le fichier est
illisible, mal formé, situé dans le dépôt, modifiable par le groupe ou les autres ou
possédé par l'uid courant (non root), situé sous un répertoire remplaçable, si une empreinte diffère, si le module chargé n'est
pas le lanceur haché ou n'utilise pas le sceau approuvé, si --approved-seal-sha256 est
passé en ligne de commande ou si --out existe déjà.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import re
import stat
import sys
import types
from pathlib import Path

sys.dont_write_bytecode = True

_HEX64 = re.compile(r"[0-9a-f]{64}")
ENV_VAR = "GENESIS_HOST_APPROVALS"
APPROVAL_KEY = "circuit2_launcher_seal_sha256"
LAUNCHER_KEY = "circuit2_launcher_sha256"
VERIFIER_KEY = "circuit2_verifier_sha256"
SEAL_PATH_KEY = "circuit2_launcher_seal_path"
LAUNCHER_NAME = "run_circuit2_campaign.py"
VERIFIER_NAME = "seal_circuit2_launcher.py"
LAUNCHER_MODULE = "run_circuit2_campaign"
VERIFIER_MODULE = "seal_circuit2_launcher"
SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[1]


class AnchorError(Exception):
    """Approbation hôte absente, non fiable, mal formée ou différente de l'empreinte du sceau."""


def _current_uid() -> int:
    """uid effectif du processus courant ; isolé pour pouvoir être simulé par les tests unitaires."""
    return os.geteuid()


def _sha256_of(path: Path, label: str) -> str:
    """Empreinte SHA-256 des octets du fichier ; lève AnchorError s'il est illisible."""
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError as exc:
        raise AnchorError(f"{label} illisible : {exc}") from exc


def _read_descriptor(fd: int) -> bytes:
    """Lit tout le contenu depuis le descripteur ouvert."""
    chunks = []
    while True:
        chunk = os.read(fd, 65536)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _directory_owners(path: Path) -> dict:
    """Propriétaires des répertoires ancêtres de path (résolu), jusqu'à '/'.

    Refuse (AnchorError) tout répertoire inscriptible par le groupe ou les autres, sauf s'il porte
    le bit sticky et appartient à root : un tel répertoire permet de remplacer le fichier par renommage.
    """
    owners = {}
    for directory in path.parents:
        try:
            info = os.stat(directory)
        except OSError as exc:
            raise AnchorError(f"répertoire illisible : {directory} : {exc}") from exc
        if info.st_mode & 0o022 and not (info.st_mode & stat.S_ISVTX and info.st_uid == 0):
            raise AnchorError(f"le répertoire {directory} est inscriptible par le groupe ou les autres")
        owners[str(directory)] = info.st_uid
    return owners


def load_host_approval() -> dict:
    """Lit et valide le fichier d'approbation hôte ; lève AnchorError s'il n'est pas fiable.

    Retourne file (chemin résolu), owner (uid propriétaire), seal, launcher et verifier
    (empreintes approuvées), seal_path (chemin résolu du sceau approuvé) et dir_owners
    (propriétaires des répertoires ancêtres). Aucun module candidat n'est importé ici.
    """
    raw = os.environ.get(ENV_VAR)
    if not raw:
        raise AnchorError(f"{ENV_VAR} est requis")
    try:
        path = Path(raw).resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise AnchorError(f"fichier d'approbation hôte illisible : {exc}") from exc
    if path.is_relative_to(REPO_ROOT.resolve()):
        raise AnchorError("le fichier d'approbation hôte ne doit pas se trouver dans le dépôt")
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError as exc:
        raise AnchorError(f"fichier d'approbation hôte illisible : {exc}") from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise AnchorError("fichier d'approbation hôte illisible : ce n'est pas un fichier régulier")
        if info.st_mode & 0o022:
            raise AnchorError("le fichier d'approbation hôte est inscriptible par le groupe ou les autres")
        content = _read_descriptor(fd)
    except OSError as exc:
        raise AnchorError(f"fichier d'approbation hôte illisible : {exc}") from exc
    finally:
        os.close(fd)
    owners = _directory_owners(path)
    try:
        data = json.loads(content.decode("utf-8"))
    except ValueError as exc:
        raise AnchorError(f"fichier d'approbation hôte illisible ou mal formé : {exc}") from exc
    if not isinstance(data, dict):
        raise AnchorError("fichier d'approbation hôte mal formé")
    digests = {}
    for name, key in (("seal", APPROVAL_KEY), ("launcher", LAUNCHER_KEY), ("verifier", VERIFIER_KEY)):
        value = data.get(key)
        if not isinstance(value, str) or not _HEX64.fullmatch(value):
            raise AnchorError(f"{key} doit être 64 caractères hexadécimaux minuscules")
        digests[name] = value
    raw_seal = data.get(SEAL_PATH_KEY)
    if not isinstance(raw_seal, str) or not raw_seal:
        raise AnchorError(f"{SEAL_PATH_KEY} est requis dans le fichier d'approbation hôte")
    seal_path = Path(raw_seal)
    if not seal_path.is_absolute():
        seal_path = REPO_ROOT / seal_path
    try:
        seal_path = seal_path.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise AnchorError(f"sceau illisible : {exc}") from exc
    return {"file": path, "owner": info.st_uid, "dir_owners": owners, "seal_path": seal_path, **digests}


def check_approved(approval: dict) -> None:
    """Lit en octets (une seule fois) le lanceur, le vérificateur et le sceau, compare aux empreintes approuvées, puis contrôle les propriétaires.

    Les empreintes sont comparées avant les propriétaires. Les octets lus du lanceur et du vérificateur sont
    conservés dans approval (launcher_source, verifier_source) avec leurs chemins : ce sont ces mêmes octets
    qui sont hachés ici puis exécutés par _import_campaign, sans seconde lecture. Rien du code candidat n'est importé ici.
    """
    launcher_path = SCRIPTS_DIR / LAUNCHER_NAME
    verifier_path = SCRIPTS_DIR / VERIFIER_NAME
    checks = (
        ("lanceur", launcher_path, approval["launcher"]),
        ("vérificateur", verifier_path, approval["verifier"]),
        ("sceau", approval["seal_path"], approval["seal"]),
    )
    sources = {}
    for name, path, expected in checks:
        try:
            data = Path(path).read_bytes()
        except OSError as exc:
            raise AnchorError(f"{name} illisible : {exc}") from exc
        if hashlib.sha256(data).hexdigest() != expected:
            raise AnchorError(f"l'empreinte du {name} ne correspond pas à l'approbation hôte")
        sources[name] = data
    approval["launcher_path"] = launcher_path
    approval["launcher_source"] = sources["lanceur"]
    approval["verifier_path"] = verifier_path
    approval["verifier_source"] = sources["vérificateur"]
    owner = approval["owner"]
    if owner != 0 and owner == _current_uid():
        raise AnchorError("le propriétaire du fichier d'approbation hôte est l'uid courant ; il doit être root ou un autre uid")
    for directory, uid in approval["dir_owners"].items():
        if uid != 0 and uid == _current_uid():
            raise AnchorError(f"le propriétaire du répertoire {directory} est l'uid courant ; il doit être root ou un autre uid")


def _load_verified(name: str, path: Path, source: bytes):
    """Crée le module name à partir des octets déjà hachés, sans mécanisme d'import ni cache de bytecode.

    Le module est enregistré dans sys.modules avant l'exécution ; l'entrée est retirée si l'exécution échoue.
    """
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    try:
        exec(compile(source, str(path), "exec"), module.__dict__)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def _import_campaign(approval: dict):
    """Charge le vérificateur puis le lanceur depuis les octets hachés par check_approved ; à n'appeler qu'après check_approved et les contrôles de --out.

    Le vérificateur est chargé en premier pour que l'import qu'en fait le lanceur résolve ce module vérifié
    et non un cache candidat. Vérifie que le module chargé est le fichier haché et utilise le sceau approuvé.
    """
    for entry in (REPO_ROOT / "src", SCRIPTS_DIR):
        if entry.is_dir() and str(entry) not in sys.path:
            sys.path.insert(0, str(entry))
    try:
        _load_verified(VERIFIER_MODULE, approval["verifier_path"], approval["verifier_source"])
        module = _load_verified(LAUNCHER_MODULE, approval["launcher_path"], approval["launcher_source"])
        module_file = Path(module.__file__).resolve()
        module_seal = Path(module.SEAL_PATH).resolve()
    except Exception as exc:
        raise AnchorError(f"module de campagne inutilisable : {exc}") from exc
    if module_file != Path(approval["launcher_path"]).resolve():
        raise AnchorError("le module de campagne chargé n'est pas le lanceur dont l'empreinte a été approuvée")
    if module_seal != approval["seal_path"]:
        raise AnchorError("le module de campagne utilise un autre sceau que celui approuvé")
    return module


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--approved-seal-sha256", default=None)
    parser.add_argument("--out", default=None)
    known, rest = parser.parse_known_args(args)
    if known.approved_seal_sha256 is not None:
        print("refus : --approved-seal-sha256 n'est pas accepté en ligne de commande ; l'approbation vient du fichier désigné par GENESIS_HOST_APPROVALS", file=sys.stderr)
        return 2
    try:
        approval = load_host_approval()
        check_approved(approval)
    except AnchorError as exc:
        print(f"refus : {exc}", file=sys.stderr)
        return 2
    if known.out is None:
        print("refus : --out est requis", file=sys.stderr)
        return 2
    out = Path(known.out)
    if out.exists():
        print(f"refus : {out} existe déjà", file=sys.stderr)
        return 2
    try:
        campaign = _import_campaign(approval)
    except AnchorError as exc:
        print(f"refus : {exc}", file=sys.stderr)
        return 2
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = campaign.main(rest)
    if code:
        return code
    try:
        result = json.loads(buffer.getvalue())
    except ValueError:
        result = None
    if not isinstance(result, dict):
        print("refus : la sortie du lanceur n'est pas un objet JSON", file=sys.stderr)
        return 2
    result["approved_seal_sha256"] = approval["seal"]
    result["approved_launcher_sha256"] = approval["launcher"]
    result["approved_verifier_sha256"] = approval["verifier"]
    result["host_approval_file"] = str(approval["file"])
    result["command"] = args
    try:
        with open(out, "x", encoding="utf-8") as handle:
            handle.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    except FileExistsError:
        print(f"refus : {out} existe déjà", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
