#!/usr/bin/env python3
"""Launch one Genesis lineage and render what it did. The sequencing belongs to the runtime.

This is a DEVELOPMENT demonstration for the stopping criterion in
``docs/METAMORPHOSIS_TARGET.md``: not that the components exist, but that **one lineage** runs them as
one program. It is not a scientific result, it is not frozen, and it advances no gate.

The script supplies a world, a lineage decision mechanism and a renderer. It does not assign lineage
state, append journal entries, run probes or decide when an accepted architectural transition becomes
durable. ``genesis.controller`` owns those effects and publishes a checkpoint after every handled
intent before it asks the mechanism for the next one.

The mechanism below is still deliberately a fixed programme rather than a search strategy. That is a
known DEVELOPMENT frontier, not something this demonstration hides.

Run it with ``--write`` to persist the rendered record under ``experiments/GENESIS/``.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis import controller  # noqa: E402
from genesis import development_bodies as bodies  # noqa: E402
from genesis import state as lineage_state  # noqa: E402
from genesis import trust_root as tr  # noqa: E402
from genesis.loop import Genesis  # noqa: E402
from genesis.migration import Substrate  # noqa: E402

RECORD_PATH = ROOT / "experiments" / "GENESIS" / "DEMONSTRATION_RECORD.json"
STATE_PATH = ROOT / "experiments" / "GENESIS" / "runtime_state"
TASKS = [{"task_id": "t%d" % index, "input": index} for index in range(8)]


def _seed_state() -> dict:
    return lineage_state.create_state(
        body_digest="s0",
        components=[
            {
                "name": name,
                "origin": "seed",
                "certificate": None,
                "provenance": tr.provenance("host_written", produced_by="seed"),
            }
            for name in ("operator_table", "signal_interface")
        ],
        vocabulary=[
            {"name": "resolvable_by_%s" % name, "origin": "seed", "certificate": None}
            for name in ("operator_table", "signal_interface")
        ],
    )


def _world() -> controller.World:
    """What exists, as the host admits it. The lineage may reach nothing outside this."""
    return controller.world(
        tasks=TASKS,
        demands={
            "spanning": bodies.SPANNING_DEMAND,
            "confusable_a": bodies.CONFUSABLE_A,
            "confusable_b": bodies.CONFUSABLE_B,
        },
        substrates={
            "record-store": Substrate(
                name="record-store", operations=bodies.SUBSTRATE_OPERATIONS
            )
        },
        probe_registry=bodies.PROBE_REGISTRY,
        component_operations=bodies.COMPONENT_OPERATIONS,
        artifacts={
            "regressed": "genesis.development_bodies:regressed_body",
            "improved": "genesis.development_bodies:improved_body",
            "translate": "genesis.development_bodies:translate_to_record_store",
            "generation_2": "genesis.development_bodies:migrated_improved_body",
            "generation_3": "genesis.development_bodies:migrated_further_body",
            "generation_4": "genesis.development_bodies:migrated_fourth_body",
        },
        grade=bodies.grade,
    )


#: The lineage's plan, as data. Each entry is one intent the executor validates and performs. This is
#: a fixed programme rather than a searched one — the mechanism is a lookup, not a strategy — and
#: saying so is the point: what this demonstration shows is that the runtime performs the
#: architectural transitions, not that the lineage discovered which ones to attempt.
PROGRAMME = (
    controller.Transform(name="regressed", body="regressed", rationale={"step": "rejected"}),
    controller.Transform(
        name=bodies.ACQUIRED_COMPONENT, body="improved", rationale={"step": "accepted"}
    ),
    controller.SeparateVocabulary(demands=("confusable_a", "confusable_b")),
    controller.AcquireComponent(demand="spanning", new_component="joint_registry"),
    controller.Migrate(
        substrate="record-store",
        probe_for=("read", "write", "list", "transact"),
        translation="translate",
        used_operations=("read",),
    ),
    controller.Transform(
        name=bodies.SECOND_ACQUISITION,
        body="generation_2",
        depends_on=bodies.ACQUIRED_COMPONENT,
        rationale={"step": "evolved after the migration"},
    ),
    controller.Transform(
        name=bodies.THIRD_ACQUISITION,
        body="generation_3",
        depends_on=bodies.SECOND_ACQUISITION,
        rationale={"step": "a second link"},
    ),
    controller.Transform(
        name=bodies.FOURTH_ACQUISITION,
        body="generation_4",
        depends_on=bodies.THIRD_ACQUISITION,
        rationale={"step": "a third link"},
    ),
)


def mechanism(context):
    """From the frozen controller context to one intent. It receives a value and returns data."""
    step = len(context.acquisitions) + context.observations + _architectural_steps(context)
    if step >= len(PROGRAMME):
        return controller.Stop(reason="the programme is finished")
    return PROGRAMME[step]


def _architectural_steps(context) -> int:
    """How many vocabulary/component acquisitions and migrations the context already shows."""
    acquired_components = sum(1 for name in context.components if name == "joint_registry")
    acquired_features = sum(1 for name in context.vocabulary if name.startswith("requires_"))
    migrated = 1 if context.body_artifact_digest in _MIGRATED_DIGESTS else 0
    return acquired_components + acquired_features + migrated


_MIGRATED_DIGESTS = frozenset(
    tr.artifact_digest_of(factory)["artifact_digest"]
    for factory in (
        bodies.migrated_parent_body,
        bodies.migrated_improved_body,
        bodies.migrated_further_body,
        bodies.migrated_fourth_body,
    )
)


def demonstrate(state_path: Path | None = None) -> dict:
    """Run the development demonstration in an explicit disposable state root.

    The CLI keeps the documented repository path. Tests must supply their own
    temporary directory so parallel workers cannot rewrite tracked evidence.
    """

    state_path = STATE_PATH if state_path is None else state_path
    if state_path.exists():
        shutil.rmtree(state_path)

    genesis = Genesis(
        state=_seed_state(),
        body_factory=bodies.parent_body,
        budget=tr.Budget(limits={"generations": 8, "probes": 4000}),
        isolation=tr.Isolation(),
        grade=bodies.grade,
    )
    run = controller.run(
        genesis,
        _world(),
        mechanism,
        max_steps=len(PROGRAMME) + 1,
        checkpoint_directory=state_path,
    )

    restored = Genesis.restore(state_path, body_factory=genesis.body_factory, grade=bodies.grade)
    survival = {
        "state_digest_matches": restored.state["state_digest"] == genesis.state["state_digest"],
        "journal_head_matches": restored.journal.head == genesis.journal.head,
        "journal_length": len(restored.journal),
        "mechanism_artifact_matches": controller.bound_mechanism_artifact(restored)
        == controller.bound_mechanism_artifact(genesis),
    }

    record = {
        "schema": "genesis-demonstration-v2",
        "development": True,
        "is_a_scientific_observation": False,
        "advances_a_generality_gate": False,
        "frozen": False,
        "architecture_sequenced_by": "genesis.controller.run",
        "persistence_sequenced_by": "genesis.controller.run",
        "run": run,
        "survives_process_death": survival,
        "journal_kinds": [entry["kind"] for entry in genesis.journal],
        "trust_root_sha256": tr.source_digest(),
        "evaluation_contract_digest": genesis.evaluation_contract["contract_digest"],
    }
    record["record_digest"] = tr.digest_of(record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="persist the demonstration record")
    arguments = parser.parse_args()
    record = demonstrate()
    if arguments.write:
        RECORD_PATH.parent.mkdir(parents=True, exist_ok=True)
        RECORD_PATH.write_bytes(tr.canonical_bytes(record) + b"\n")
        print("wrote %s" % RECORD_PATH.relative_to(ROOT))
    for step in record["run"]["steps"]:
        print(
            "  %-22s %s"
            % (step["intent"], {k: v for k, v in step.items() if k != "intent"})
        )
    print(
        json.dumps(
            {
                key: record["run"][key]
                for key in (
                    "final_generation",
                    "final_components",
                    "final_vocabulary",
                    "causal_chain",
                )
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
