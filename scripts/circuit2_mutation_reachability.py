#!/usr/bin/env python3
"""Accessibilité par mutation de seed_procedure (circuit 2, budget 16).

Question : une ou deux mutations légales de seed_procedure peuvent-elles
admettre les vecteurs de traits candidats sans perdre l'admission des
vecteurs déjà admis ? Une réponse positive ne serait qu'une condition
d'accessibilité, pas une preuve de progrès RSI.

Hors réseau, sans modèle. Seul cp.run évalue l'admission. Les mutations sont
énumérées via cp.mutate elle-même, avec un faux rng « à bande » (BandRNG) qui
rejoue un préfixe de choix et explore en profondeur d'abord toutes les
branches : chaque feuille correspond à un appel réel à cp.mutate.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from genesis import circuit_meta_lineage as lineage  # noqa: E402
from genesis import circuit_procedure as cp  # noqa: E402

SCHEMA = "circuit2-mutation-reachability-v1"
RESULTS_DIR = REPO_ROOT / "results"
TARGETS_PATH = RESULTS_DIR / "circuit2_budget16_traits_s0_g1.json"
TARGET_PARAMS = ("support", "arity", "nands", "composed")

MAX_CALLS = 10000
MAX_SECONDS = 60.0
SAMPLE_SEEDS = (0, 1, 2)
MAX_WITNESSES_PER_CATEGORY = 20
EXHAUSTIVE_RESERVE_DIVISOR = 4
EXHAUSTIVE_TIME_SHARE = 0.75
EXPLORATION_TIME_SHARE = 0.8

NOTE_SAMPLE = "échantillon, non exhaustif"
NOTE_NO_WITNESS_SAMPLE = "aucun témoin dans l'échantillon, rien conclu"
CONCLUSION_POSITIVE = (
    "des témoins conservateurs vérifiés existent : condition d'accessibilité "
    "seulement, pas une preuve de progrès RSI"
)
CONCLUSION_NON_EVALUEE = (
    "admission sans conservation évaluée pour au moins un témoin : "
    "rien conclu sur l'accessibilité"
)
CONCLUSION_ADMISSION_SEULE = (
    "admission seule : des procédures admettent une cible mais la conservation "
    "de la référence est réfutée ; pas de condition d'accessibilité établie"
)
CONCLUSION_AUCUN_EXHAUSTIF = "aucun témoin : énumération exhaustive des profondeurs 1 et 2"
CONCLUSION_PREPARATION_INTERROMPUE = (
    "préparation interrompue par le plafond de temps : référence non établie, "
    "rien conclu"
)
_ERROR = object()


class ReachabilityError(Exception):
    """Erreur explicite d'entrée ou de configuration."""


class Budget:
    """Compteur global d'appels à cp.mutate et plafond de temps."""

    def __init__(self, max_calls, deadline):
        self.max_calls = max_calls
        self.deadline = deadline
        self.calls = 0
        self.hit_calls = False
        self.hit_time = False

    def allow(self, limit=None, deadline=None):
        lim = self.max_calls if limit is None else min(limit, self.max_calls)
        dl = self.deadline if deadline is None else min(deadline, self.deadline)
        if self.calls >= lim:
            self.hit_calls = True
            return False
        if time.monotonic() >= dl:
            self.hit_time = True
            return False
        return True


class BandRNG:
    """Faux rng : rejoue un préfixe de choix, puis prend 0 (ou tire dans source)."""

    def __init__(self, prefix=(), source=None):
        self.prefix = list(prefix)
        self.source = source
        self.trace = []

    def _pick(self, n):
        if n <= 0:
            raise ValueError("choix sur un ensemble vide")
        k = len(self.trace)
        if k < len(self.prefix):
            i = self.prefix[k]
            if not 0 <= i < n:
                raise ValueError("choix hors bande")
        elif self.source is not None:
            i = self.source.randrange(n)
        else:
            i = 0
        self.trace.append((i, n))
        return i

    def choice(self, seq):
        return seq[self._pick(len(seq))]

    def randrange(self, *args):
        r = range(*args)
        return r[self._pick(len(r))]


def explore_exhaustive(fn, ctl, limit_calls, deadline, on_leaf):
    """Parcours en profondeur d'abord de toutes les branches de choix de fn.

    Retourne True si l'exploration est complète, False si un plafond l'a
    interrompue. Chaque feuille consomme un appel du budget.
    """
    stack = [[]]
    while stack:
        if not ctl.allow(limit_calls, deadline):
            return False
        prefix = stack.pop()
        rng = BandRNG(prefix)
        ctl.calls += 1
        result = fn(rng)
        chosen = [i for i, _ in rng.trace]
        on_leaf(chosen, result)
        for pos in range(len(prefix), len(rng.trace)):
            for alt in range(rng.trace[pos][1] - 1, 0, -1):
                stack.append(chosen[:pos] + [alt])
    return True


def _digest_and_record(proc):
    record = cp.to_record(proc)
    blob = json.dumps(record, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest(), record


def is_valid(proc):
    try:
        res = cp.validate(proc)
    except Exception:
        return False
    if res is None or res is True:
        return True
    if res is False:
        return False
    if isinstance(res, (list, tuple, set, dict, str)):
        return len(res) == 0
    return bool(res)


def admits(proc, vec):
    return bool(cp.run(proc, vec)[1])


def get_seed():
    seed = cp.seed_procedure
    return seed() if callable(seed) else seed


def replay(seed, path):
    proc = seed
    for step in path:
        proc = cp.mutate(copy.deepcopy(proc), BandRNG(step))
    return proc


def vec_key(vec):
    try:
        return json.dumps(vec, sort_keys=True, default=list)
    except TypeError:
        return repr(vec)


def load_targets(path=None):
    path = TARGETS_PATH if path is None else Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ReachabilityError(f"lecture impossible de {path} : {exc}") from exc
    cands = data.get("candidats") if isinstance(data, dict) else None
    if not cands:
        raise ReachabilityError(f"{path} : clé 'candidats' absente ou vide")
    targets = []
    for idx, cand in enumerate(cands):
        sources = [cand.get("traits"), cand] if isinstance(cand, dict) else []
        params = {}
        for key in TARGET_PARAMS:
            for src in sources:
                if isinstance(src, dict) and key in src:
                    params[key] = src[key]
                    break
            else:
                raise ReachabilityError(f"candidat {idx} : paramètre '{key}' introuvable")
        vec = cp.traits_of(
            params["support"], params["arity"], params["nands"], params["composed"]
        )
        targets.append({"nom": f"cible_{idx}", "parametres": params, "vec": vec})
    return targets


def build_domain(extra_vectors):
    domain = {}
    skipped = 0
    for composed in (False, True):
        for size in range(cp.MAX_STEPS + 1):
            for support in range(lineage.SUPPORT_CAP + 1):
                try:
                    vec = lineage._traits(size, support, composed)
                except Exception:
                    skipped += 1
                    continue
                domain.setdefault(vec_key(vec), vec)
    for vec in extra_vectors:
        domain.setdefault(vec_key(vec), vec)
    return domain, skipped


def _explore_level(depth, parents, seen, ctl, allow_exhaustive, leave_half):
    ctl.hit_calls = False
    ctl.hit_time = False
    calls0 = ctl.calls
    stats = {"doublons": 0, "erreurs_mutation": 0, "invalides": 0}
    new = {}

    def make_fn(parent):
        def fn(rng):
            try:
                return cp.mutate(copy.deepcopy(parent["proc"]), rng)
            except Exception:
                return _ERROR

        return fn

    def consume(parent, chosen, child):
        if child is _ERROR:
            stats["erreurs_mutation"] += 1
            return
        if not is_valid(child):
            stats["invalides"] += 1
            return
        digest, record = _digest_and_record(child)
        if digest in seen:
            stats["doublons"] += 1
            return
        entry = {
            "proc": child,
            "digest": digest,
            "record": record,
            "path": parent["path"] + [chosen],
            "depth": depth,
        }
        seen[digest] = entry
        new[digest] = entry

    complete = False
    if allow_exhaustive:
        now = time.monotonic()
        remaining = max(0, ctl.max_calls - ctl.calls)
        limit = ctl.calls + remaining - remaining // EXHAUSTIVE_RESERVE_DIVISOR
        dl = now + max(0.0, ctl.deadline - now) * EXHAUSTIVE_TIME_SHARE
        complete = True
        for parent in parents:
            done = explore_exhaustive(
                make_fn(parent),
                ctl,
                limit,
                dl,
                lambda ch, res, p=parent: consume(p, ch, res),
            )
            if not done:
                complete = False
                break
    if not complete:
        limit = dl = None
        if leave_half:
            now = time.monotonic()
            remaining = max(0, ctl.max_calls - ctl.calls)
            limit = ctl.calls + remaining - remaining // 2
            dl = now + max(0.0, ctl.deadline - now) / 2
        rngs = [random.Random(s) for s in SAMPLE_SEEDS]
        turn = 0
        while parents and ctl.allow(limit, dl):
            src = rngs[turn % len(rngs)]
            turn += 1
            parent = parents[src.randrange(len(parents))]
            rng = BandRNG(source=src)
            ctl.calls += 1
            child = make_fn(parent)(rng)
            consume(parent, [i for i, _ in rng.trace], child)
    entries = sorted(new.values(), key=lambda e: e["digest"])
    level = {
        "profondeur": depth,
        "mode": "exhaustif" if complete else "échantillon",
        "note": (
            "énumération exhaustive de tous les choix de cp.mutate"
            if complete
            else NOTE_SAMPLE
        ),
        "appels_utilises": ctl.calls - calls0,
        "procedures_distinctes": len(entries),
        "bornes_atteintes": {"appels": ctl.hit_calls, "temps": ctl.hit_time},
        "invalides": stats["invalides"],
        "doublons": stats["doublons"],
        "erreurs_mutation": stats["erreurs_mutation"],
    }
    return level, entries, complete


def _category(witnesses):
    return {
        "total": len(witnesses),
        "affiches": min(len(witnesses), MAX_WITNESSES_PER_CATEGORY),
        "liste": witnesses[:MAX_WITNESSES_PER_CATEGORY],
    }


def _lecture(mode, n_conservateurs, n_refutes, n_non_evalues, n_procedures_non_evaluees):
    """Lecture d'un niveau ; le négatif exhaustif exige un niveau entièrement évalué."""
    reste = ""
    if n_procedures_non_evaluees:
        reste = (
            f" ; {n_procedures_non_evaluees} procédure(s) du niveau non évaluée(s) : "
            "le niveau n'est pas entièrement évalué"
        )
    if n_conservateurs:
        return (
            f"{n_conservateurs} témoin(s) conservateur(s) vérifié(s) : condition "
            "d'accessibilité seulement, pas une preuve de progrès RSI"
        ) + reste
    if n_refutes or n_non_evalues:
        return (
            f"admission sans conservation vérifiée ({n_refutes} réfutée(s), "
            f"{n_non_evalues} non évaluée(s)) : aucune accessibilité positive établie"
        ) + reste
    if n_procedures_non_evaluees:
        return (
            f"rien n'est conclu pour ce niveau : {n_procedures_non_evaluees} "
            "procédure(s) non évaluée(s), évaluation interrompue"
        )
    if mode == "exhaustif":
        return "aucun témoin à ce niveau (énumération exhaustive des choix de cp.mutate)"
    return NOTE_NO_WITNESS_SAMPLE


def _conclusion(n_conservateurs, n_refutes, n_non_evalues, exhaustive):
    """Conclusion pure : positive seulement avec un témoin conservateur vérifié."""
    if n_conservateurs > 0:
        return CONCLUSION_POSITIVE
    if n_non_evalues > 0:
        return CONCLUSION_NON_EVALUEE
    if n_refutes > 0:
        return CONCLUSION_ADMISSION_SEULE
    if exhaustive:
        return CONCLUSION_AUCUN_EXHAUSTIF
    return NOTE_NO_WITNESS_SAMPLE


def _statut(conserves):
    if conserves is True:
        return "conservee"
    if conserves is False:
        return "refutee"
    return "non_evaluee"


def _expired(ctl):
    return time.monotonic() >= ctl.deadline


def _evaluate(proc, targets, reference, ctl):
    """Évalue une procédure ; l'échéance est contrôlée avant chaque cp.run."""
    admit = {t["nom"]: None for t in targets}
    for target in targets:
        if _expired(ctl):
            return admit, None, True
        admit[target["nom"]] = admits(proc, target["vec"])
    if not any(v is True for v in admit.values()):
        return admit, None, False
    for vec in reference:
        if _expired(ctl):
            return admit, None, True
        if not admits(proc, vec):
            return admit, False, False
    return admit, True, False


def _niveaux_preparation_interrompue():
    """Niveaux vides d'un rapport dont la préparation a été interrompue."""
    return [
        {
            "profondeur": depth,
            "mode": "échantillon",
            "note": NOTE_SAMPLE,
            "appels_utilises": 0,
            "procedures_distinctes": 0,
            "bornes_atteintes": {"appels": False, "temps": True},
            "invalides": 0,
            "doublons": 0,
            "erreurs_mutation": 0,
            "temoins": 0,
            "admission_seule_refutee": 0,
            "conservation_non_evaluee": 0,
            "procedures_non_evaluees": 0,
            "lecture": CONCLUSION_PREPARATION_INTERROMPUE,
        }
        for depth in (1, 2)
    ]


def analyse():
    """Retourne (rapport, état interne) ; l'état sert aux tests."""
    start = time.monotonic()
    seed = get_seed()
    targets = load_targets()
    preparation_deadline = start + MAX_SECONDS
    interrompue = False
    for target in targets:
        if time.monotonic() >= preparation_deadline:
            interrompue = True
            break
        if admits(seed, target["vec"]):
            raise ReachabilityError(
                f"{target['nom']} est déjà admis par seed_procedure : question sans objet"
            )
    domain, skipped = build_domain([t["vec"] for t in targets])
    reference = []
    if not interrompue:
        for vec in domain.values():
            if time.monotonic() >= preparation_deadline:
                interrompue = True
                break
            if admits(seed, vec):
                reference.append(vec)
    if interrompue:
        reference = []

    ctl = Budget(MAX_CALLS, start + MAX_SECONDS * EXPLORATION_TIME_SHARE)
    seed_digest, seed_record = _digest_and_record(seed)
    seed_entry = {
        "proc": seed,
        "digest": seed_digest,
        "record": seed_record,
        "path": [],
        "depth": 0,
    }
    seen = {seed_digest: seed_entry}
    if interrompue:
        level1, level2 = _niveaux_preparation_interrompue()
        entries1, entries2 = [], []
        complete1 = complete2 = False
    else:
        level1, entries1, complete1 = _explore_level(1, [seed_entry], seen, ctl, True, True)
        level2, entries2, complete2 = _explore_level(2, entries1, seen, ctl, complete1, False)
    entries = entries1 + entries2
    ctl.deadline = start + MAX_SECONDS

    witnesses = []
    per_depth = {
        d: {"conservee": 0, "refutee": 0, "non_evaluee": 0, "procedures_non_evaluees": 0}
        for d in (1, 2)
    }
    procedures_non_evaluees = 0
    for entry in entries:
        admit, conserves, interrupted = _evaluate(
            entry["proc"], targets, reference, ctl
        )
        if interrupted:
            procedures_non_evaluees += 1
            per_depth[entry["depth"]]["procedures_non_evaluees"] += 1
        if not any(v is True for v in admit.values()):
            continue
        statut = _statut(conserves)
        per_depth[entry["depth"]][statut] += 1
        witnesses.append(
            {
                "profondeur": entry["depth"],
                "chemin": entry["path"],
                "digest": entry["digest"],
                "record": entry["record"],
                "admet": admit,
                "statut_conservation": statut,
                "conserve_reference": conserves,
            }
        )

    levels = [level1, level2]
    for level in ([] if interrompue else levels):
        counts = per_depth[level["profondeur"]]
        level["temoins"] = counts["conservee"]
        level["admission_seule_refutee"] = counts["refutee"]
        level["conservation_non_evaluee"] = counts["non_evaluee"]
        level["procedures_non_evaluees"] = counts["procedures_non_evaluees"]
        level["lecture"] = _lecture(
            level["mode"],
            counts["conservee"],
            counts["refutee"],
            counts["non_evaluee"],
            counts["procedures_non_evaluees"],
        )

    temoins = {}
    conservateurs = {}
    for target in targets:
        ws = [w for w in witnesses if w["admet"][target["nom"]] is True]
        temoins[target["nom"]] = _category(ws)
        conservateurs[target["nom"]] = _category(
            [w for w in ws if w["conserve_reference"] is True]
        )

    n_conservateurs = sum(c["conservee"] for c in per_depth.values())
    n_refutes = sum(c["refutee"] for c in per_depth.values())
    n_non_evalues = sum(c["non_evaluee"] for c in per_depth.values())
    conclusion = _conclusion(
        n_conservateurs, n_refutes, n_non_evalues,
        complete1 and complete2 and procedures_non_evaluees == 0,
    )
    if interrompue:
        conclusion = CONCLUSION_PREPARATION_INTERROMPUE

    report = {
        "schema": SCHEMA,
        "methode": {
            "enumeration": (
                "faux rng à bande (choice, randrange) rejouant un préfixe de choix "
                "et explorant en profondeur d'abord toutes les branches ; chaque "
                "feuille = un appel réel à cp.mutate sur une copie de la procédure"
            ),
            "evaluation": "cp.run exclusivement ; admission = deuxième élément du triplet",
            "deduplication": (
                "sha256 du JSON canonique de cp.to_record ; chemin de mutation le "
                "plus court conservé (profondeur 1 avant 2, seed exclue)"
            ),
            "echantillonnage": (
                "si un niveau n'est pas énuméré exhaustivement : résultats partiels "
                "conservés puis tirages random.Random(0), (1), (2) en alternance, "
                "sous le même plafond global ; mode « échantillon »"
            ),
            "partage_budget": (
                "énumération exhaustive limitée à 3/4 du budget restant et du temps "
                "restant ; le reste sert à l'échantillonnage ; l'échantillonnage du "
                "niveau 1 laisse la moitié du restant au niveau 2"
            ),
            "chemin": "par étape, suite des indices de choix de la bande (rejouable)",
        },
        "bornes": {
            "max_appels": MAX_CALLS,
            "max_secondes": MAX_SECONDS,
            "part_temps_exploration": EXPLORATION_TIME_SHARE,
            "graines_echantillon": list(SAMPLE_SEEDS),
            "temoins_max_par_categorie": MAX_WITNESSES_PER_CATEGORY,
            "lecture_bornes_atteintes": (
                "vrai si un plafond (global ou part de phase) a arrêté une phase du niveau"
            ),
        },
        "cibles": [
            {"nom": t["nom"], "parametres": t["parametres"], "traits": t["vec"]}
            for t in targets
        ],
        "domaine": {
            "taille": len(domain),
            "taille_reference": len(reference),
            "combinaisons_ignorees": skipped,
            "description": (
                "vecteurs distincts de lineage._traits(size, support, composed) pour "
                "composed dans (False, True), size de 0 à cp.MAX_STEPS, support de 0 à "
                "lineage.SUPPORT_CAP (façon dont step() construit les traits ; borne "
                "supérieure, la taille minimale réelle n'est pas établie), union avec "
                "les vecteurs cibles ; référence = vecteurs du domaine admis par "
                "seed_procedure"
            ),
        },
        "appels_total": ctl.calls,
        "niveaux": levels,
        "temoins": temoins,
        "temoins_conservateurs": conservateurs,
        "admission_seule_refutee": n_refutes,
        "conservation_non_evaluee": n_non_evalues,
        "procedures_non_evaluees": procedures_non_evaluees,
        "evaluation_interrompue": procedures_non_evaluees > 0 or interrompue,
        "preparation_interrompue": interrompue,
        "conclusion": conclusion,
    }
    state = {
        "seed": seed,
        "seed_digest": seed_digest,
        "targets": targets,
        "reference": reference,
        "entries": entries,
        "calls": ctl.calls,
    }
    return report, state


def build_report():
    return analyse()[0]


def _check_out(raw):
    path = Path(raw).resolve()
    root = RESULTS_DIR.resolve()
    try:
        path.relative_to(root)
    except ValueError:
        raise ReachabilityError(f"--out doit être sous {root}") from None
    if path == root:
        raise ReachabilityError("--out doit désigner un fichier")
    if path.exists():
        raise ReachabilityError(f"{path} existe déjà : refus d'écraser")
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", help="nouveau fichier sous results/ (mode 'x')")
    args = parser.parse_args(argv)
    try:
        out_path = _check_out(args.out) if args.out else None
        report = build_report()
    except ReachabilityError as exc:
        print(f"erreur : {exc}", file=sys.stderr)
        return 1
    text = json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False, default=str)
    if out_path is None:
        sys.stdout.write(text + "\n")
        return 0
    try:
        with open(out_path, "x", encoding="utf-8") as handle:
            handle.write(text + "\n")
    except OSError as exc:
        print(f"erreur : {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
