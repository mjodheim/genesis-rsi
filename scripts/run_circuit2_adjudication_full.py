"""Lanceur mince de l'adjudication CIRCUIT2 à l'échelle complète.

Charge le plan gelé, le vérifie, puis délègue à adjudicate_circuit_lineage.main
avec les graines et les générations du plan. Rien n'est redéfini ici : budgets,
seuils et bras viennent du plan et du script existant.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import adjudicate_circuit_lineage as adj  # noqa: E402
import freeze_circuit2_plan as fcp  # noqa: E402

DEFAULT_OUT_NAME = "circuit2_adjudication_full.json"


class WrapperError(Exception):
    """Demande refusée par le lanceur."""


def _results_dir():
    return (Path(adj.ROOT) / "results").resolve()


def resolve_out(value=None):
    """Sortie par défaut, ou --out à condition de rester sous results/."""
    results = _results_dir()
    if value is None:
        return results / DEFAULT_OUT_NAME
    path = Path(value)
    if not path.is_absolute():
        path = Path(adj.ROOT) / path
    path = path.resolve()
    try:
        path.relative_to(results)
    except ValueError:
        raise WrapperError(f"--out doit rester sous {results}") from None
    if path == results:
        raise WrapperError("--out doit désigner un fichier sous results/")
    return path


def load_verified_plan():
    """Charge le plan gelé et le vérifie ; lève une exception s'il est altéré."""
    plan = adj.load_plan(adj.DEFAULT_PLAN)
    if fcp.verify_plan(plan) is False:
        raise WrapperError("plan gelé non conforme")
    return plan


def build_argv(plan, out):
    """Arguments de adjudicate_circuit_lineage.main, tous tirés du plan."""
    return (
        ["--seeds"] + [str(seed) for seed in plan["seeds"]]
        + ["--generations", str(plan["budgets"]["generations"])]
        + ["--out", str(out)]
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Adjudication CIRCUIT2 complète, paramétrée par le plan gelé."
    )
    parser.add_argument(
        "--out",
        default=None,
        help="sortie JSON, obligatoirement sous results/",
    )
    args = parser.parse_args(argv)
    try:
        out = resolve_out(args.out)
        plan = load_verified_plan()
    except Exception as exc:  # refus : aucun appel à adj.main
        print(f"erreur : {exc}", file=sys.stderr)
        return 2
    return adj.main(build_argv(plan, out))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
