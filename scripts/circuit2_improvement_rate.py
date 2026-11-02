"""validation technique seulement.

Mesure descriptive de la variation des scores de génération d'un bras
du circuit 2. Aucun seuil, aucun verdict : le module ne conclut rien.
Stdlib uniquement ; aucun effet à l'import.

Les enregistrements sont ceux écrits par run_circuit2_arms.run_arm ;
seuls 'score' (None ou [résolues, -évaluations]) et 'exhausted' sont lus.
"""
import math


def _is_number(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _check_score(score, index):
    if score is None:
        return None
    if not isinstance(score, (list, tuple)) or len(score) != 2:
        raise ValueError(f"enregistrement {index} : score de forme invalide")
    if not all(_is_number(x) for x in score):
        raise ValueError(f"enregistrement {index} : composante de score invalide")
    return (score[0], score[1])


def improvement_rate(records):
    """Moyenne des différences de résolues entre générations consécutives.

    Une paire (i, i+1) n'est comptée que si les deux scores sont non None ;
    sinon elle est listée dans skipped_pairs (ni imputation ni interpolation).
    La différence sur -évaluations est rapportée à part.
    """
    if not isinstance(records, (list, tuple)):
        raise ValueError("records doit être une liste")
    scores = []
    exhausted_generations = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"enregistrement {index} : dict attendu")
        if "score" not in record:
            raise ValueError(f"enregistrement {index} : champ 'score' absent")
        scores.append(_check_score(record["score"], index))
        if record.get("exhausted"):
            exhausted_generations.append(index)
    resolved_deltas = []
    neg_eval_deltas = []
    skipped_pairs = []
    for i in range(len(scores) - 1):
        before, after = scores[i], scores[i + 1]
        if before is None or after is None:
            skipped_pairs.append((i, i + 1))
            continue
        resolved_deltas.append(after[0] - before[0])
        neg_eval_deltas.append(after[1] - before[1])
    n_deltas = len(resolved_deltas)
    n_none = sum(1 for s in scores if s is None)
    return {
        "rate": sum(resolved_deltas) / n_deltas if n_deltas else None,
        "n_deltas": n_deltas,
        "n_none": n_none,
        "skipped_pairs": skipped_pairs,
        "exhausted_generations": exhausted_generations,
        "incomplete": n_none > 0,
        "mean_neg_evaluations_delta": (
            sum(neg_eval_deltas) / n_deltas if n_deltas else None),
    }
