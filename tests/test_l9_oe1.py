"""OE1 persistent open-ended research tests."""
from experiment.l9_oe1.curriculum import frontier, propose
from experiment.l9_oe1.improver import ImproverGenome
from experiment.l9_oe1.qd import BehaviorProfile, DOMINANCE_RADIUS, QDArchive, behavior_distance
from experiment.l9_oe1.replay import replay_task
from experiment.l9_oe1 import online, native_online
from experiment.rsi_v51.memory import ExperimentalMemory
from experiment.rsi_v52.abstractions import AbstractionMemory
from experiment.rsi_v53 import bank as v53_bank
from experiment.rsi_v36 import bank as v36_bank
from experiment.l9_oe1.store import ExperienceStore


def test_improver_mutations_change_one_policy_knob():
    root = ImproverGenome()
    children = root.mutate_one()
    assert children
    assert len({child.sha256() for child in children}) == len(children)
    assert all(child.sha256() != root.sha256() for child in children)


def test_store_persists_graph_edges_in_sqlite(tmp_path):
    store = ExperienceStore(f"sqlite:///{tmp_path / 'oe1.db'}")
    genome = ImproverGenome()
    improver = store.upsert_improver(genome)
    run = store.create_run(code_sha="abc", scope="test")
    task = {"family": "affine", "width": 4, "window": 0, "inputs": [0, 1], "target": {"width": 4, "rotation": 1, "mask": 1}}
    row = {
        "position": 0,
        "root_evaluation": {"quality_milli": 500},
        "programs": [
            {
                "source_sha256": "root",
                "genome": {"width": 4, "rotation": 0, "mask": 0},
                "quality_milli": 500,
                "candidate_origin": "search",
                "search_parent_source_sha256": None,
            },
            {
                "source_sha256": "child",
                "genome": {"width": 4, "rotation": 1, "mask": 0},
                "quality_milli": 750,
                "candidate_origin": "scaffold",
                "search_parent_source_sha256": "root",
            },
        ],
    }
    task_sha = store.record_episode(
        run_id=run, improver_sha256=improver, task=task, row=row
    )
    graph = store.task_graph(task_sha)
    assert {node["candidate_sha256"] for node in graph} == {"root", "child"}
    child = next(node for node in graph if node["candidate_sha256"] == "child")
    assert child["parent_candidate_sha256"] == "root"
    edges = store.task_edges(task_sha)
    assert any(
        edge["parent_candidate_sha256"] == "root"
        and edge["child_candidate_sha256"] == "child"
        for edge in edges
    )
    store.close()


def test_replay_never_uses_candidate_quality_for_priority():
    genome = ImproverGenome(replay_budget=1)
    rows = [
        {
            "candidate_sha256": "root",
            "parent_candidate_sha256": None,
            "origin": "search",
            "quality_milli": 500,
            "descriptor_json": "{}",
        },
        {
            "candidate_sha256": "scaffold",
            "parent_candidate_sha256": "root",
            "origin": "scaffold",
            "quality_milli": 600,
            "descriptor_json": "{}",
        },
        {
            "candidate_sha256": "search",
            "parent_candidate_sha256": "root",
            "origin": "search",
            "quality_milli": 1000,
            "descriptor_json": "{}",
        },
    ]
    outcome = replay_task(rows, genome)
    # With one call the policy prefers scaffold by origin even though the hidden
    # search child would have solved the task. This guards against replay leakage.
    assert outcome["evaluated_candidates"] == ["scaffold"]
    assert outcome["solved"] is False


def test_qd_archive_preserves_behavioural_stepping_stones():
    a = BehaviorProfile(frozenset({"a", "b"}), 10.0, 0.2, 0.50)
    b = BehaviorProfile(frozenset({"c", "d"}), 10.0, 0.2, 0.49)
    assert behavior_distance(a, b) > DOMINANCE_RADIUS
    archive = QDArchive(max_size=8)
    ok_a, _ = archive.add("a", a, learning_progress=0.1)
    ok_b, _ = archive.add("b", b, learning_progress=0.1)
    assert ok_a and ok_b
    assert {elite.improver_sha256 for elite in archive.elites} == {"a", "b"}


def test_curriculum_moves_to_competence_frontier():
    rows = [
        {"family": "rotation", "width": 8, "solved": True},
        {"family": "rotation", "width": 8, "solved": True},
        {"family": "rotation", "width": 9, "solved": True},
        {"family": "rotation", "width": 9, "solved": False},
    ]
    zones = frontier(rows)
    assert zones[0][:2] == ("rotation", 9)
    tasks = propose(rows, seed=123, count=4)
    assert all(task["family"] == "rotation" for task in tasks)
    assert all(task["width"] == 9 for task in tasks)


def test_replay_honours_extra_multi_parent_edges():
    genome = ImproverGenome(replay_budget=2)
    graph = {
        "nodes": [
            {
                "candidate_sha256": "root",
                "parent_candidate_sha256": None,
                "origin": "search",
                "quality_milli": 500,
                "genome_json": '{"width":4,"rotation":0,"mask":0}',
            },
            {
                "candidate_sha256": "a",
                "parent_candidate_sha256": "root",
                "origin": "search",
                "quality_milli": 550,
                "genome_json": '{"width":4,"rotation":1,"mask":0}',
            },
            {
                "candidate_sha256": "b",
                "parent_candidate_sha256": "root",
                "origin": "scaffold",
                "quality_milli": 900,
                "genome_json": '{"width":4,"rotation":2,"mask":0}',
            },
            {
                "candidate_sha256": "child",
                "parent_candidate_sha256": "a",
                "origin": "counterfactual",
                "quality_milli": 1000,
                "genome_json": '{"width":4,"rotation":2,"mask":1}',
            },
        ],
        "edges": [
            {
                "parent_candidate_sha256": "b",
                "child_candidate_sha256": "child",
                "relation": "counterfactual",
            }
        ],
    }
    outcome = replay_task(graph, genome)
    assert outcome["evaluated_candidates"] == ["b", "child"]
    assert outcome["solved"] is True


def test_online_oe1_keeps_real_evaluator_cap(tmp_path):
    exact = ExperimentalMemory(tmp_path / "oe1-exact.db")
    abstract = AbstractionMemory(tmp_path / "oe1-abstract.db")
    task = v53_bank.stream(v53_bank.FRESH_SEEDS[0])[0]
    row = online.episode(task, 0, exact, abstract, isolated=False)
    assert row["charged_evaluations"] <= online.MAX_EVALUATIONS
    assert row["oe1"]["search_budget"] == online.SEARCH_BUDGET
    assert row["programs"][0]["candidate_origin"] == "root"
    exact.close()
    abstract.close()


def test_native_online_keeps_fourteen_call_cap():
    task = v36_bank.stream(
        v36_bank.DEV_SEEDS[0],
        "relational-sql",
        epochs=1,
        tasks_per_epoch=4,
    )[0]
    row = native_online.episode(
        task,
        0,
        {},
        arm="archive",
        isolated=False,
    )
    assert row["charged_evaluations"] <= native_online.MAX_EVALUATIONS
    assert row["oe1"]["max_depth"] == 12
