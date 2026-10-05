"""OE1 persistent open-ended research tests."""
from experiment.l9_oe1.curriculum import frontier, propose
from experiment.l9_oe1.improver import ImproverGenome
from experiment.l9_oe1.qd import BehaviorProfile, DOMINANCE_RADIUS, QDArchive, behavior_distance
from experiment.l9_oe1.replay import replay_task
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
