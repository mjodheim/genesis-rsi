"""Complete public DEVELOPMENT populations, with cumulative legacy retention."""
from itertools import product

from experiment.rsi_v25.commitments import digest, digest_bytes
from experiment.rsi_v25.search_engine import Caps, global_utility
from experiment.rsi_v26.development import Host as LegacyHost, population as legacy_population
from experiment.rsi_v27.engine import run_search
from experiment.rsi_v28.family import ROOT_PARAMS, render, universe

PUBLIC_CAPS = Caps(requests=9, rounds=8, parallelism=2, mutation_depth=4)


def original_population(stage):
    if stage == 0:
        return tuple({"family": "plateau", "decoy_quality": decoy, "winning_quality": quality,
                      "winner_position": position, "winning_depth": depth, "width": width,
                      "decoy_depth": tail} for decoy, quality, position, depth, width, tail in product(
                          (650, 900), (250, 500), (0, 1, 2), (2, 3), (3, 5), (3, 4)))
    if stage == 1:
        return tuple({"family": "complement", "partial_quality": quality, "width": width,
                      "correct_position": position, "repeated_mutations": repeated, "first_axis": axis}
                     for quality, width, position, repeated, axis in product(
                         (350, 650), (2, 4), (0, 1, 2), (2, 4), ("a", "b")))
    if stage == 2:
        return tuple({"family": "scheduling", "partial_quality": quality, "width": width,
                      "winner_position": position, "correct_position": correct, "decoy_depth": tail}
                     for quality, width, position, correct, tail in product(
                         (650, 850, 950), (4, 6), (0, 1, 2, 3), (0, 1, 2), (2, 4)))
    raise ValueError("Unknown public development phase")


def population(stage):
    from experiment.rsi_v27.fresh_bank import BANKS as consumed_v27_banks
    return (*original_population(stage), *consumed_v27_banks[stage])


class Host:
    forbidden_tokens = []

    def __init__(self, spec):
        self.spec, self.edges, self.rows = spec, {}, {}
        self.add("root", 0, [])
        family = spec["family"]
        self.edges["root"] = []
        for i in range(spec["width"]):
            token = f"r{i}"
            if family == "complement":
                axes = [spec["first_axis"]]
                self.add(token, spec["partial_quality"], axes)
                self.edges[token] = []
                for j in range(spec["repeated_mutations"]):
                    child = token + f"-repeat{j}"
                    self.add(child, spec["partial_quality"], axes)
                    self.edges[token].append(child)
                for j in range(3):
                    child = token + f"-pair{j}"
                    quality = 1000 if j == spec["correct_position"] else spec["partial_quality"] + 50
                    self.add(child, quality, ["a", "b"])
                    self.edges[token].append(child)
            else:
                winning = i == spec["winner_position"]
                quality = (spec["winning_quality"] if family == "plateau"
                           else spec["partial_quality"] - 200) if winning else (
                               spec["decoy_quality"] if family == "plateau" else 400)
                self.add(token, quality, ["a"])
                if family == "scheduling" and winning:
                    self.edges[token] = []
                    for j in range(3):
                        child = token + f"-step{j}"
                        self.add(child, spec["partial_quality"] if j == spec["correct_position"] else quality, ["a"])
                        self.edges[token].append(child)
                        if j == spec["correct_position"]:
                            final = child + "-done"
                            self.add(final, 1000, ["a"])
                            self.edges[child] = [final]
                else:
                    depth = spec["winning_depth"] if winning else spec["decoy_depth"]
                    previous = token
                    for d in range(2, depth + 1):
                        child = token + f"-d{d}"
                        value = 1000 if winning and d == depth else quality + (100 if winning else 0)
                        self.add(child, value, ["a"])
                        self.edges[previous] = [child]
                        previous = child
            self.edges["root"].append(token)

    def add(self, token, quality, axes):
        self.rows[token] = {"candidate": {"token": token}, "source_sha256": digest([self.spec, token]),
                            "quality_milli": quality, "axes": axes}

    def root(self):
        return self.rows["root"]

    def children(self, candidate, depth):
        if depth >= PUBLIC_CAPS.mutation_depth:
            return ()
        return tuple(self.rows[token] for token in self.edges.get(candidate["token"], ()))

    def action(self, row):
        return {"family": "public-graph", "target_axes": row["axes"],
                "mechanisms": ["represented-mutation"], "changed_regions": row["axes"]}

    def evaluate(self, row):
        return {"accepted": True, "source_sha256": row["source_sha256"],
                "quality_milli": row["quality_milli"], "public_task_sha256": digest(self.spec)}


def episodes(source, stage):
    rows = []
    for old in legacy_population():
        search = run_search(source, LegacyHost(old), caps=PUBLIC_CAPS, isolated=False)
        rows.append(summary(search, digest(["v26-retention", old])))
    for index in range(stage + 1):
        for spec in population(index):
            search = run_search(source, Host(spec), caps=PUBLIC_CAPS, isolated=False)
            rows.append(summary(search, digest(spec)))
    return rows


def phase_episodes(row, stage):
    count = len(legacy_population()) + sum(len(population(i)) for i in range(stage + 1))
    return row["episodes"][:count]


def summary(search, task_hash):
    return {"accepted": search["accepted"], "episode_sha256": task_hash,
            "best_quality_milli": search["best_quality_milli"],
            "represented_requests": search["represented_requests"], "rounds": search["rounds"],
            "observations_sha256": digest(search["observations"])}


def calibration():
    candidates = []
    for row in universe():
        source = render(row["params"])
        results = episodes(source, 2)
        phases = []
        for stage in range(3):
            count = len(legacy_population()) + sum(len(population(i)) for i in range(stage + 1))
            phases.append({"stage": stage, "utility": global_utility(results[:count]), "episode_count": count})
        candidates.append({**row, "phases": phases, "episodes": results})
        print("Public development source " + str(len(candidates)) + "/81", flush=True)
    return {"schema": "mira-genesis-v28-development-calibration-v1",
            "scope": "PUBLIC_DEVELOPMENT_WITH_DISCLOSED_CONSUMED_V27_TASKS", "holdout_consumed": False,
            "parent_sha256": digest_bytes(render(ROOT_PARAMS).encode()),
            "candidate_count": len(candidates), "population_counts": [len(population(i)) for i in range(3)],
            "candidates": candidates}
