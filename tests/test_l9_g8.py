"""G8 scheduler acquisition tests."""
from experiment.l9_oe1 import g8_family, g8_macro
from experiment.rsi_v25.commitments import digest_bytes
from experiment.rsi_v38 import bank as v38_bank


def test_g8_root_is_exact_qualified_g7():
    source = g8_family.render_source(g8_family.ROOT_PARAMS)
    assert digest_bytes(source.encode()) == g8_family.G7_SHA256
    assert source == g8_family.parent_source()


def test_weighted_descendant_is_executable_and_distinct():
    params = {**g8_family.ROOT_PARAMS, "strategy": "weighted"}
    source = g8_family.render_source(params)
    assert digest_bytes(source.encode()) != g8_family.G7_SHA256
    compile(source, "<g8-test>", "exec")
    functions = {}
    exec(compile(source, "<g8-test>", "exec"), functions)
    assert callable(functions["select_parent_batch"])
    assert callable(functions["order_candidates"])


def test_g8_macro_episode_stays_inside_cap():
    task = v38_bank.stream(
        v38_bank.DEV_SEEDS[0], "relational-sql",
        epochs=1, tasks_per_epoch=4,
    )[0]
    row = g8_macro.episode(
        task, 0, {}, g8_family.parent_source(), isolated=False
    )
    assert row["charged_evaluations"] <= g8_macro.CAP
    assert row["policy_sha256"] == g8_family.G7_SHA256
