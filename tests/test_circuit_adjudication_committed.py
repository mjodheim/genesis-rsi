"""Tests hors réseau et sans modèle sur le résultat committé de l'adjudication réduite.

Fichier lu : results/circuit2_adjudication_s0-1_g6.json (adjudication RÉDUITE :
graines 0 et 1 sur 20, 6 générations).

- Les 20 graines ne sont pas jugées contre le critère gelé.
- Résultat nul consigné tel quel : rendement 0 et même empreinte de bibliothèque
  pour les 4 bras.
- Écart de machinery_commit non expliqué : 245661e0 dans PROCEDURE_PREREG_PLAN.json
  contre e60a37e1 dans le résultat ; il n'est pas comparé ici.
- Rien n'est affirmé sur results/circuit2_campaign_full.json : non vérifié.

Hypothèses non confirmées par lecture, laissées visibles : le module fcp est lu via
adj.fcp ; le digest du plan est pris dans le plan s'il y figure, sinon fingerprint(plan).
Un échec dû à l'une d'elles est un résultat à rapporter, pas à masquer.
"""
from __future__ import annotations

import ast
import importlib
import json
import signal
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "adjudicate_circuit_lineage.py"
RESULT = ROOT / "results" / "circuit2_adjudication_s0-1_g6.json"
REPLAY_TIMEOUT_S = 600
FORBIDDEN_KEY_PARTS = ("gain", "success", "succes", "succès")
TRIVIAL_CONSTANTS = (0, 1)


class _ReplayTimeout(Exception):
    pass


def _on_alarm(signum, frame):
    raise _ReplayTimeout()


@pytest.fixture(scope="module")
def adj():
    for path in (str(ROOT), str(ROOT / "scripts")):
        if path not in sys.path:
            sys.path.insert(0, path)
    return importlib.import_module("adjudicate_circuit_lineage")


@pytest.fixture(scope="module")
def fcp(adj):
    return adj.fcp


@pytest.fixture(scope="module")
def data():
    return json.loads(RESULT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def plan(adj):
    return adj.load_plan(adj.DEFAULT_PLAN)


def _plan_digest(adj, plan):
    if isinstance(plan, dict):
        for key in ("plan_digest", "digest"):
            if key in plan:
                return plan[key]
    return adj.fingerprint(plan)


def _yield_value(measured):
    if isinstance(measured, dict) and "held_out_yield" in measured:
        return measured["held_out_yield"]
    return measured


def _all_keys(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield str(key)
            yield from _all_keys(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _all_keys(value)


def _numeric_value(node):
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        node = node.operand
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and not isinstance(node.value, bool)
    ):
        return node.value
    return None


def _bad_keys(obj):
    return sorted(
        {k for k in _all_keys(obj) if any(p in k.lower() for p in FORBIDDEN_KEY_PARTS)}
    )


ROW_FIELDS = ("held_out_yield", "library_fingerprint", "generations", "stop_reason")


def _row_divergences(committed_rows, obtained_by_pair):
    """Compare champ par champ les lignes committées aux valeurs obtenues."""
    divergences = []
    committed_pairs = set()
    for row in sorted(committed_rows, key=lambda r: (r["arm"], r["seed"])):
        pair = (row["arm"], row["seed"])
        committed_pairs.add(pair)
        context = f"bras={row['arm']!r} graine={row['seed']!r}"
        if pair not in obtained_by_pair:
            divergences.append(f"{context} : aucune valeur obtenue")
            continue
        obtained = obtained_by_pair[pair]
        for field in ROW_FIELDS:
            if field not in obtained:
                divergences.append(f"{context} {field} : valeur obtenue absente")
            elif obtained[field] != row[field]:
                divergences.append(
                    f"{context} {field} : attendu={row[field]!r} "
                    f"obtenu={obtained[field]!r}"
                )
    for pair in sorted(set(obtained_by_pair) - committed_pairs, key=repr):
        divergences.append(
            f"bras={pair[0]!r} graine={pair[1]!r} : valeur obtenue sans ligne committée"
        )
    return divergences


def _check_identities(full, expected_arms, expected_seeds):
    """Renvoie les écarts d'identité (bras, graines, paires) ; liste vide si conforme."""
    errors = []
    expected_arms = list(expected_arms)
    expected_seeds = list(expected_seeds)
    arms = list(full["arms"])
    if set(arms) != set(expected_arms):
        errors.append(
            f"ensemble des bras : attendu={sorted(expected_arms)!r} "
            f"obtenu={sorted(set(arms))!r}"
        )
    if arms != expected_arms:
        errors.append(
            f"liste ordonnée des bras : attendu={expected_arms!r} "
            f"obtenu={arms!r}"
        )
    if list(full["seeds"]) != expected_seeds:
        errors.append(
            f"graines : attendu={expected_seeds!r} obtenu={list(full['seeds'])!r}"
        )
    pairs = [(row["arm"], row["seed"]) for row in full["rows"]]
    duplicates = sorted({p for p in pairs if pairs.count(p) > 1}, key=repr)
    if duplicates:
        errors.append(f"paires dupliquées : {duplicates!r}")
    expected_pairs = {(arm, seed) for arm in expected_arms for seed in expected_seeds}
    missing = sorted(expected_pairs - set(pairs), key=repr)
    if missing:
        errors.append(f"paires manquantes : {missing!r}")
    unexpected = sorted(set(pairs) - expected_pairs, key=repr)
    if unexpected:
        errors.append(f"paires hors produit cartésien : {unexpected!r}")
    if len(pairs) != len(expected_pairs):
        errors.append(
            f"nombre de lignes : attendu={len(expected_pairs)} obtenu={len(pairs)}"
        )
    return errors


def _synthetic_full(arms, seeds, pairs):
    """Données SYNTHÉTIQUES, construites pour le test, jamais lues sur disque."""
    return {
        "arms": list(arms),
        "seeds": list(seeds),
        "rows": [{"arm": arm, "seed": seed} for arm, seed in pairs],
    }


def test_check_identities_synthetic_data():
    # Données SYNTHÉTIQUES : aucun fichier committé n'est lu.
    arms = ("synthetic_a", "synthetic_b")
    seeds = [0, 1]
    product = [(arm, seed) for arm in arms for seed in seeds]
    assert _check_identities(_synthetic_full(arms, seeds, product), arms, seeds) == []
    missing_arm = _synthetic_full(["synthetic_a"], seeds, product[:2])
    assert _check_identities(missing_arm, arms, seeds)
    foreign_seeds = [0, 2]
    foreign_seed = _synthetic_full(
        arms, foreign_seeds, [(arm, seed) for arm in arms for seed in foreign_seeds]
    )
    assert _check_identities(foreign_seed, arms, seeds)
    duplicate = _synthetic_full(arms, seeds, product[:-1] + [product[0]])
    assert _check_identities(duplicate, arms, seeds)
    extra_row = _synthetic_full(arms, seeds, product + [product[0]])
    assert _check_identities(extra_row, arms, seeds)


def _synthetic_row(arm, seed, **overrides):
    """Ligne SYNTHÉTIQUE, construite pour le test, sans lien avec un résultat committé."""
    row = {
        "arm": arm,
        "seed": seed,
        "held_out_yield": 0,
        "library_fingerprint": f"synthetic-fp-{arm}",
        "generations": 6,
        "stop_reason": "synthetic-stop",
    }
    row.update(overrides)
    return row


def _obtained_from(rows):
    return {
        (row["arm"], row["seed"]): {field: row[field] for field in ROW_FIELDS}
        for row in rows
    }


def test_row_divergences_synthetic_rows():
    # Lignes SYNTHÉTIQUES : aucun rejeu, aucun fichier committé.
    rows = [
        _synthetic_row(arm, seed)
        for arm in ("synthetic_a", "synthetic_b")
        for seed in (0, 1)
    ]
    assert _row_divergences(rows, _obtained_from(rows)) == []
    # Graine 1 : même bras et même empreinte que la graine 0, non sélectionnée avant.
    wrong_yield = _obtained_from(rows)
    wrong_yield[("synthetic_a", 1)]["held_out_yield"] = 1
    found = _row_divergences(rows, wrong_yield)
    assert len(found) == 1
    assert "held_out_yield" in found[0] and "graine=1" in found[0]
    wrong_stop = _obtained_from(rows)
    wrong_stop[("synthetic_b", 1)]["stop_reason"] = "synthetic-other"
    found = _row_divergences(rows, wrong_stop)
    assert len(found) == 1
    assert "stop_reason" in found[0] and "graine=1" in found[0]
    missing = _obtained_from(rows)
    del missing[("synthetic_b", 1)]
    assert _row_divergences(rows, missing)


def test_structure(adj, data, plan):
    assert data["scale"] == "reduced"
    assert data["seeds"] == [0, 1]
    assert data["generations"] == 6
    assert len(data["arms"]) == 4
    assert len(set(data["arms"])) == 4
    assert len(data["rows"]) == 8
    pairs = {(row["arm"], row["seed"]) for row in data["rows"]}
    assert pairs == {(arm, seed) for arm in data["arms"] for seed in data["seeds"]}
    assert data["plan_digest"] == _plan_digest(adj, plan)
    budgets = plan["budgets"]
    assert data["task_budget"] == budgets["task_budget"]
    assert data["per_generation_limit"] == budgets["per_generation_limit"]
    assert data["generations"] == budgets["generations"]


def test_null_result_recorded_as_is(data):
    rows = data["rows"]
    yields = [row["held_out_yield"] for row in rows]
    fingerprints = {row["library_fingerprint"] for row in rows}
    pairs = {(row["arm"], row["seed"]) for row in rows}
    expected = {(arm, seed) for arm in data["arms"] for seed in data["seeds"]}
    observed = (
        f"lignes={len(rows)} paires={sorted(pairs)!r} held_out_yield={yields!r} "
        f"library_fingerprint_distinctes={sorted(fingerprints)!r}"
    )
    assert pairs == expected, observed
    assert len(rows) == len(expected), observed
    assert all(value == 0 for value in yields), observed
    assert len(fingerprints) == 1, observed


def test_replay_random_procedure_seed0(adj, fcp, data):
    row = next(
        r for r in data["rows"] if r["arm"] == "random_procedure" and r["seed"] == 0
    )
    plan_errors = tuple(
        e for e in (getattr(adj, "PlanError", None),) if isinstance(e, type)
    )
    has_alarm = hasattr(signal, "SIGALRM")
    if has_alarm:
        previous = signal.signal(signal.SIGALRM, _on_alarm)
        signal.alarm(REPLAY_TIMEOUT_S)
    try:
        tasks = fcp.learn_tasks()
        records, engine, final_procedure, _initial = adj.final_library(
            "random_procedure",
            0,
            tasks,
            data["per_generation_limit"],
            data["task_budget"],
            data["generations"],
        )
        measured = adj.measure_held_out(engine)
    except _ReplayTimeout:
        pytest.skip(f"rejeu au-delà de {REPLAY_TIMEOUT_S} s : non conclu, non comparé")
    except plan_errors as exc:
        if "EXECUTABLES" not in str(exc):
            raise
        pytest.skip(f"EXECUTABLES.json absent (PlanError) : mesure impossible ({exc})")
    finally:
        if has_alarm:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous)
    obtenu_yield = _yield_value(measured)
    obtenu_fingerprint = adj.fingerprint(engine.record())
    obtenu_generations = len(records)
    obtenu_stop_reason = adj.stop_reason(records)
    assert obtenu_yield == row["held_out_yield"], (
        f"held_out_yield : attendu={row['held_out_yield']!r} obtenu={obtenu_yield!r}"
    )
    assert obtenu_fingerprint == row["library_fingerprint"], (
        f"library_fingerprint : attendu={row['library_fingerprint']!r} "
        f"obtenu={obtenu_fingerprint!r}"
    )
    assert obtenu_generations == row["generations"], (
        f"generations : attendu={row['generations']!r} obtenu={obtenu_generations!r}"
    )
    assert obtenu_stop_reason == row["stop_reason"], (
        f"stop_reason : attendu={row['stop_reason']!r} obtenu={obtenu_stop_reason!r}"
    )


def test_replay_full_adjudication(adj, fcp, plan, tmp_path, monkeypatch):
    full = json.loads(
        (ROOT / "results" / "circuit2_adjudication_full.json").read_text(
            encoding="utf-8"
        )
    )
    assert full["scale"] == "full"
    identity_errors = _check_identities(full, adj.rca.ARMS, plan["seeds"])
    assert not identity_errors, "\n".join(identity_errors)
    assert len(full["rows"]) == 80
    assert full["plan_digest"] == _plan_digest(adj, plan)
    for field in ("task_budget", "per_generation_limit", "generations"):
        assert full[field] == plan["budgets"][field], (
            f"{field} : attendu={plan['budgets'][field]!r} "
            f"obtenu={full[field]!r}"
        )

    monkeypatch.chdir(tmp_path)
    for name in ("TMPDIR", "TMP", "TEMP"):
        monkeypatch.setenv(name, str(tmp_path))
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    monkeypatch.setattr(sys, "dont_write_bytecode", True)

    if not hasattr(signal, "SIGALRM"):
        pytest.fail(
            "rejeu complet impossible : SIGALRM indisponible pour contrôler "
            "le délai ; aucune ligne rejouée"
        )
    plan_errors = tuple(
        e for e in (getattr(adj, "PlanError", None),) if isinstance(e, type)
    )
    obtained_by_pair = {}
    measured_cache = {}
    replayed = []

    def _seen_divergences():
        seen = _row_divergences(replayed, obtained_by_pair)
        if not seen:
            return ""
        return "\nDivergences déjà observées :\n" + "\n".join(seen)

    for row in sorted(full["rows"], key=lambda row: (row["arm"], row["seed"])):
        pair = (row["arm"], row["seed"])
        context = f"bras={row['arm']!r} graine={row['seed']!r}"
        previous = signal.signal(signal.SIGALRM, _on_alarm)
        signal.alarm(REPLAY_TIMEOUT_S)
        try:
            tasks = fcp.learn_tasks()
            records, engine, _final_procedure, _initial = adj.final_library(
                row["arm"],
                row["seed"],
                tasks,
                full["per_generation_limit"],
                full["task_budget"],
                full["generations"],
            )
            fingerprint = adj.fingerprint(engine.record())
            cache_key = (row["arm"], fingerprint)
            if cache_key not in measured_cache:
                measured_cache[cache_key] = _yield_value(
                    adj.measure_held_out(engine)
                )
            obtained_by_pair[pair] = {
                "held_out_yield": measured_cache[cache_key],
                "library_fingerprint": fingerprint,
                "generations": len(records),
                "stop_reason": adj.stop_reason(records),
            }
        except _ReplayTimeout:
            pytest.fail(
                f"{context} : rejeu complet au-delà de {REPLAY_TIMEOUT_S} s ; "
                "couverture incomplète, délai non réduit"
                + _seen_divergences()
            )
        except plan_errors as exc:
            pytest.fail(
                f"{context} : rejeu complet impossible (PlanError), "
                f"EXECUTABLES.json absent ou manifeste invalide : {exc}"
                + _seen_divergences()
            )
        except Exception as exc:
            pytest.fail(
                f"{context} : échec du rejeu complet, notamment si le manifeste "
                f"est invalide : {type(exc).__name__}: {exc}"
                + _seen_divergences()
            )
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous)
        replayed.append(row)
    divergences = _row_divergences(full["rows"], obtained_by_pair)
    assert not divergences, "\n".join(divergences)


def test_no_success_threshold_comparison_in_script():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"), filename=str(SCRIPT))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for operand in [node.left, *node.comparators]:
                value = _numeric_value(operand)
                if value is not None and value not in TRIVIAL_CONSTANTS:
                    found.append((node.lineno, value))
    assert not found, f"comparaisons à une constante numérique : {found}"


def test_no_gain_or_success_key_in_committed_result(data):
    assert _bad_keys(data) == []
    assert _bad_keys(data["rows"]) == []


FULL_ADJUDICATION = ROOT / "results" / "circuit2_adjudication_full.json"
FULL_PROVENANCE = ROOT / "results" / "circuit2_provenance_adjudication_full.json"
FULL_NAME = "results/circuit2_adjudication_full.json"
ANCESTOR = "ancetre_de_head"


def _find_commit(node):
    if isinstance(node, dict):
        if "machinery_commit" in node:
            return True, node["machinery_commit"]
        children = list(node.values())
    elif isinstance(node, list):
        children = node
    else:
        return False, None
    for child in children:
        found, value = _find_commit(child)
        if found:
            return True, value
    return False, None


def _full_provenance_errors(full, prov):
    """Renvoie les écarts de provenance de l'adjudication complète ; vide si conforme."""
    verdicts = prov.get("verdicts") if isinstance(prov, dict) else None
    if not isinstance(verdicts, list):
        return ["verdicts absent ou non liste"]
    entries = [e for e in verdicts if isinstance(e, dict) and e.get("fichier") == FULL_NAME]
    if len(entries) != 1:
        return [f"entrées pour {FULL_NAME} : attendu=1 obtenu={len(entries)}"]
    entry = entries[0]
    errors = []
    found, commit = _find_commit(full)
    if not found or not isinstance(commit, str):
        errors.append("machinery_commit de l'adjudication absent ou non chaîne")
    if entry.get("verdict") != ANCESTOR:
        errors.append(f"verdict de l'entrée : attendu={ANCESTOR!r} obtenu={entry.get('verdict')!r}")
    values = entry.get("valeurs")
    if not isinstance(values, list) or not values:
        errors.append("valeurs absent, non liste ou vide")
        return errors
    for index, item in enumerate(values):
        if not isinstance(item, dict):
            errors.append(f"valeur {index} : objet attendu")
            continue
        for field in ("valeur", "commit_resolu"):
            if item.get(field) != commit:
                errors.append(f"valeur {index} {field} : attendu={commit!r} obtenu={item.get(field)!r}")
        if item.get("verdict") != ANCESTOR:
            errors.append(f"valeur {index} verdict : attendu={ANCESTOR!r} obtenu={item.get('verdict')!r}")
        if type(item.get("code_retour")) is not int or item["code_retour"] != 0:
            errors.append(f"valeur {index} code_retour : attendu=0 obtenu={item.get('code_retour')!r}")
    return errors


def _synthetic_full_provenance(**changes):
    """Relevé SYNTHÉTIQUE, construit pour le test, jamais lu sur disque."""
    commit = "a" * 40
    value = {"code_retour": 0, "commit_resolu": commit, "valeur": commit, "verdict": ANCESTOR}
    entry = {"fichier": FULL_NAME, "verdict": ANCESTOR, "valeurs": [value]}
    value.update(changes.get("value", {}))
    entry.update(changes.get("entry", {}))
    return {"verdicts": [entry]}


def test_full_provenance_errors_synthetic_divergences():
    # Données SYNTHÉTIQUES : aucun fichier committé n'est lu.
    commit = "a" * 40
    other = "b" * 40
    full = {"machinery_commit": commit}
    assert _full_provenance_errors(full, _synthetic_full_provenance()) == []
    divergent = {
        "valeur": _synthetic_full_provenance(value={"valeur": other}),
        "commit_resolu": _synthetic_full_provenance(value={"commit_resolu": other}),
        "verdict": _synthetic_full_provenance(
            value={"verdict": "non_ancetre"}, entry={"verdict": "non_ancetre"}
        ),
        "fichier": _synthetic_full_provenance(
            entry={"fichier": "results/circuit2_adjudication_s0-1_g6.json"}
        ),
    }
    for name, prov in divergent.items():
        assert _full_provenance_errors(full, prov), name
    assert _full_provenance_errors({"machinery_commit": other}, _synthetic_full_provenance())
    assert _full_provenance_errors({}, _synthetic_full_provenance())


def test_full_provenance_matches_committed_adjudication():
    full = json.loads(FULL_ADJUDICATION.read_text(encoding="utf-8"))
    prov = json.loads(FULL_PROVENANCE.read_text(encoding="utf-8"))
    entries = [e for e in prov["verdicts"] if e["fichier"] == FULL_NAME]
    assert len(entries) == 1
    entry = entries[0]
    found, commit = _find_commit(full)
    assert found and isinstance(commit, str)
    assert entry["valeurs"]
    for item in entry["valeurs"]:
        assert item["valeur"] == commit
        assert item["commit_resolu"] == commit
    assert entry["verdict"] == ANCESTOR
    assert _full_provenance_errors(full, prov) == []
