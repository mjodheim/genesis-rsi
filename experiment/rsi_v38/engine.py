"""Recursive program-valued macros; derived from the preserved V37 constructor."""
from experiment.rsi_v25.commitments import digest
from experiment.rsi_v35 import native
from experiment.rsi_v36 import engine as prior
from experiment.rsi_v36.engine import history_from, summary
from experiment.rsi_v38 import bank


ARMS = ("archive", "archive-ancestor", "greedy", "cold")


def cap(task):
    return 26


def width(task, arm):
    return max(1, task["slots"] // (4 if arm == "archive-ancestor" else 2))


def frontiers(history, domain, arm, slots):
    mapped = "archive" if arm == "archive-ancestor" else arm
    return prior.frontiers(history, domain, mapped, slots)


def fragments(history, domain, arm, slots, block_width):
    if arm == "cold":
        return []
    mapped = "archive" if arm == "archive-ancestor" else arm
    donors = prior.successful(history, domain, mapped, slots)
    if arm != "greedy":
        donors = [entry for entry in donors if len(entry["genome"]["ops"]) == block_width]
    donors.sort(key=lambda entry: (entry["first_success_position"], entry["source_sha256"]))
    found = {}
    for entry in donors:
        ops = entry["genome"]["ops"]
        for start in range(0, len(ops) - block_width + 1, block_width):
            fragment = tuple(ops[start:start + block_width])
            if all(fragment):
                found.setdefault(fragment, {"ops": list(fragment), "donor_source_sha256": entry["source_sha256"],
                    "donor_block_start": start, "acquired_position": entry["first_success_position"]})
    return [found[key] for key in sorted(found)[:32]]


class BudgetBoundary(Exception):
    """Stop before an unpaid execution, retaining all previously paid calls."""


class Constructor:
    def __init__(self, task, history, arm, *, isolated=True, replay=None):
        bank.validate_task(task)
        if arm not in ARMS:
            raise ValueError("Unknown construction arm")
        self.task, self.history, self.arm = task, history, arm
        self.isolated, self.replay, self.calls, self.decisions = isolated, replay, [], []
        self.width = width(task, arm)
        self.learned = fragments(history, task["domain"], arm, task["slots"], self.width)
        null = native.genome(task["domain"], [])
        self.current = self.evaluate(null, {"kind": "root"})
        observed = [self.current]
        self.screen_calls = 0
        for entry in frontiers(history, task["domain"], arm, task["slots"]):
            measured = self.evaluate(entry["genome"], {"kind": "screen"})
            self.screen_calls += 1
            observed.append(measured)
            if self.exact(measured):
                break
        self.current = min(observed, key=lambda row: (
            -row["evaluation"]["matched_slots"], len(row["genome"]["ops"]), row["evaluation"]["source_sha256"]))
        self.selected_root_sha256 = self.current["evaluation"]["source_sha256"]

    def exact(self, row):
        return row["evaluation"]["matched_slots"] == self.task["slots"]

    def evaluate(self, genome, construction):
        # Leave one paid call available for confirmation, including a last-call solve.
        if len(self.calls) >= cap(self.task) - int(construction["kind"] != "verify"):
            raise BudgetBoundary
        genome = native.validate(genome)
        kind = construction["kind"]
        if self.replay is None:
            evaluation = native.evaluate(self.task, genome, isolated=self.isolated)
        else:
            if len(self.calls) >= len(self.replay):
                raise ValueError("Replay requested an unobserved execution")
            old = self.replay[len(self.calls)]
            if old["genome"] != genome or old["construction"] != construction:
                raise ValueError("Altered paid construction or donor order")
            evaluation = old["evaluation"]
        row = {"kind": kind, "genome": genome, "construction": construction, "evaluation": evaluation}
        self.calls.append(row)
        return row

    def body(self, current, start, values):
        ops = current["genome"]["ops"] + [0] * (self.task["slots"] - len(current["genome"]["ops"]))
        return native.genome(self.task["domain"], ops[:start] + values + ops[start + len(values):])

    def choose(self, before, observations, start, width):
        # Only scalar observations and public source identities enter this decision.
        candidates = [before, *observations]
        chosen = min(candidates, key=lambda row: (-row["evaluation"]["matched_slots"], row["evaluation"]["source_sha256"]))
        self.decisions.append({"start": start, "width": width,
            "observations": [{"source_sha256": row["evaluation"]["source_sha256"],
                              "matched_slots": row["evaluation"]["matched_slots"]} for row in candidates],
            "chosen_source_sha256": chosen["evaluation"]["source_sha256"]})
        self.current = chosen
        return chosen

    def point(self, slot):
        before = self.current
        parent = before["evaluation"]["source_sha256"]
        observations = []
        for operator in range(5):
            measured = self.evaluate(self.body(before, slot, [operator]),
                {"kind": "point", "slot": slot, "operator": operator, "parent_source_sha256": parent})
            observations.append(measured)
            if self.exact(measured):
                self.choose(before, observations, slot, 1)
                return
        self.choose(before, observations, slot, 1)

    def block(self, start):
        before = self.current
        parent = before["evaluation"]["source_sha256"]
        baseline = self.evaluate(self.body(before, start, [0] * self.width),
            {"kind": "block-null", "block_start": start, "parent_source_sha256": parent})
        observations = [baseline]
        for fragment in self.learned:
            measured = self.evaluate(self.body(before, start, fragment["ops"]),
                {"kind": "learned-splice", "block_start": start, "parent_source_sha256": parent, **fragment})
            observations.append(measured)
            if self.exact(measured):
                self.choose(before, observations, start, self.width)
                return
        best = self.choose(before, observations, start, self.width)
        if best["evaluation"]["matched_slots"] - baseline["evaluation"]["matched_slots"] < self.width:
            for slot in range(start, start + self.width):
                self.point(slot)
                if self.exact(self.current):
                    break

    def construct(self):
        if self.exact(self.current):
            return "screen_exact"
        try:
            if self.task["slots"] > 1 and self.learned:
                for start in range(0, self.task["slots"], self.width):
                    self.block(start)
                    if self.exact(self.current):
                        return "construction_exact"
            else:
                for slot in range(self.task["slots"]):
                    self.point(slot)
                    if self.exact(self.current):
                        return "construction_exact"
        except BudgetBoundary:
            return "external_fixed_budget"
        return "coordinates_exhausted"


def episode(task, global_position, history, arm, *, isolated=True, replay=None):
    constructor = Constructor(task, history, arm, isolated=isolated, replay=None if replay is None else replay["calls"])
    stop = constructor.construct()
    successes = [call for call in constructor.calls if constructor.exact(call)]
    if successes:
        verification = constructor.evaluate(successes[0]["genome"], {"kind": "verify"})
        if verification["evaluation"] != successes[0]["evaluation"]:
            raise ValueError("Exact body failed native re-execution")
    if len(constructor.calls) > cap(task):
        raise ValueError("Dimensioned cap exceeded")
    if replay is not None and len(constructor.calls) != len(replay["calls"]):
        raise ValueError("Omitted paid execution")
    programs = {}
    for call in constructor.calls:
        sha = call["evaluation"]["source_sha256"]
        if sha in programs:
            if programs[sha]["evaluation"] != call["evaluation"]:
                raise ValueError("Conflicting duplicate output")
            continue
        old = history.get(sha)
        parent = call["construction"].get("parent_source_sha256")
        programs[sha] = {"genome": call["genome"], "source_sha256": sha,
            "semantic_sha256": native.descriptor(call["genome"])["semantic_sha256"],
            "parent_source_sha256": old["parent_source_sha256"] if old else parent,
            "search_parent_source_sha256": parent, "evaluation": call["evaluation"],
            "previously_observed": old is not None, "construction": call["construction"],
            "donor_source_sha256": call["construction"].get("donor_source_sha256")}
    solved = [p for p in programs.values() if p["evaluation"]["matched_slots"] == task["slots"]]
    old_solved = {entry["semantic_sha256"] for entry in history.values() if entry["successes"]}
    return {"task_sha256": digest(task), "global_position": global_position, "epoch": task["epoch"],
        "domain": task["domain"], "slots": task["slots"], "calls": constructor.calls,
        "construction_decisions": constructor.decisions, "stop_reason": stop,
        "candidate_cap": cap(task), "macro_width": constructor.width, "programs": list(programs.values()),
        "selected_root_sha256": constructor.selected_root_sha256, "screen_calls": constructor.screen_calls,
        "learned_fragments": constructor.learned, "charged_evaluations": len(constructor.calls),
        "policy_calls": 0, "host_authored_coordinate_scheduler": True, "solved": bool(solved),
        "archive_size_before": len(history),
        "new_first_solving_semantics": [p["semantic_sha256"] for p in solved if p["semantic_sha256"] not in old_solved],
        "new_source_solves": [p["source_sha256"] for p in solved if p["source_sha256"] not in history],
        "rediscovered": [p["semantic_sha256"] for p in solved if p["source_sha256"] in history
            and history[p["source_sha256"]]["successes"]
            and history[p["source_sha256"]]["last_success_position"] < global_position - 1]}


def verify_episode(task, position, history, arm, row, *, isolated=True):
    if row["task_sha256"] != digest(task) or row["global_position"] != position:
        raise ValueError("Substituted task or position")
    for call in row["calls"]:
        expected = native.receipt(task, call["genome"],
            native.execute(call["genome"], task["inputs"], task["slots"], isolated=False), isolated=isolated)
        if expected != call["evaluation"]:
            raise ValueError("Altered native output/reference receipt")
    rebuilt = episode(task, position, history, arm, isolated=isolated, replay=row)
    if digest(rebuilt) != digest(row):
        raise ValueError("Altered constructor decision, ancestry, novelty or accounting")
    return True
