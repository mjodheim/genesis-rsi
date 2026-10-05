"""Multi-generation open-ended meta-search for OE1."""
from __future__ import annotations

import json

from experiment.l9_oe1.development import _profile, _task_metadata, load_graphs
from experiment.l9_oe1.improver import ImproverGenome
from experiment.l9_oe1.qd import QDArchive
from experiment.l9_oe1.replay import replay_suite


def _rank_key(result):
    return (
        result["solved"],
        -result["evaluations"],
        result["quality_milli"],
    )


def evolve(
    store,
    *,
    generations=4,
    parents_per_generation=4,
    archive_size=64,
):
    graphs = load_graphs(store)
    meta = _task_metadata(store)
    root = ImproverGenome()

    archive = QDArchive(max_size=archive_size)
    genomes = {}
    results = {}
    profiles = {}
    parent_of = {}
    generation_of = {}

    def evaluate(genome, *, parent_sha=None, generation=0):
        sha = genome.sha256()
        if sha in results:
            return sha, False

        result = replay_suite(graphs, genome)
        profile = _profile(store, result, meta)
        progress = (
            profile.quality - profiles[parent_sha].quality
            if parent_sha in profiles else 0.0
        )
        stored_sha = store.upsert_improver(
            genome,
            parent_sha256=parent_sha,
            generation=generation,
        )
        accepted, elite = archive.add(
            stored_sha,
            profile,
            learning_progress=progress,
        )
        genomes[stored_sha] = genome
        results[stored_sha] = result
        profiles[stored_sha] = profile
        parent_of[stored_sha] = parent_sha
        generation_of[stored_sha] = generation
        return stored_sha, accepted

    root_sha, _ = evaluate(root, generation=0)
    history = []

    for generation in range(1, generations + 1):
        parents = archive.parents(
            root,
            count=min(parents_per_generation, len(archive.elites)),
        )
        proposals = {}
        for elite in parents:
            parent_sha = elite.improver_sha256
            parent_genome = genomes[parent_sha]
            for child in parent_genome.mutate_one():
                sha = child.sha256()
                if sha in results or sha in proposals:
                    continue
                proposals[sha] = (child, parent_sha)

        accepted = 0
        for child, parent_sha in proposals.values():
            _, was_accepted = evaluate(
                child,
                parent_sha=parent_sha,
                generation=generation,
            )
            accepted += int(was_accepted)

        best_sha = max(results, key=lambda sha: _rank_key(results[sha]))
        history.append({
            "generation": generation,
            "parents": [elite.improver_sha256 for elite in parents],
            "proposals": len(proposals),
            "archive_accepts": accepted,
            "archive_size": len(archive.elites),
            "best_improver_sha256": best_sha,
            "best_solved": results[best_sha]["solved"],
            "best_evaluations": results[best_sha]["evaluations"],
            "best_quality_milli": results[best_sha]["quality_milli"],
        })
        if not proposals:
            break

    archive.persist(store)

    ranked = sorted(
        results,
        key=lambda sha: _rank_key(results[sha]),
        reverse=True,
    )
    top = []
    for sha in ranked[:12]:
        profile = profiles[sha]
        elite = next(
            (e for e in archive.elites if e.improver_sha256 == sha),
            None,
        )
        top.append({
            "improver_sha256": sha,
            "generation": generation_of[sha],
            "parent_sha256": parent_of[sha],
            "genome": genomes[sha].canonical(),
            "solved": results[sha]["solved"],
            "evaluations": results[sha]["evaluations"],
            "quality_milli": results[sha]["quality_milli"],
            "profile_quality": profile.quality,
            "novelty": elite.novelty if elite else None,
            "learning_progress": elite.learning_progress if elite else None,
            "in_archive": elite is not None,
        })

    return {
        "tasks": len(graphs),
        "generations": history,
        "evaluated_improvers": len(results),
        "archive_size": len(archive.elites),
        "root": {
            "improver_sha256": root_sha,
            "solved": results[root_sha]["solved"],
            "evaluations": results[root_sha]["evaluations"],
            "quality_milli": results[root_sha]["quality_milli"],
        },
        "top": top,
    }


def main(argv=None):
    import argparse
    from experiment.l9_oe1.store import ExperienceStore

    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--generations", type=int, default=4)
    parser.add_argument("--parents", type=int, default=4)
    args = parser.parse_args(argv)

    store = ExperienceStore(args.dsn)
    try:
        result = evolve(
            store,
            generations=args.generations,
            parents_per_generation=args.parents,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
    finally:
        store.close()


if __name__ == "__main__":
    main()
