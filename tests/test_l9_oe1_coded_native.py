from experiment.l9_oe1 import coded_native
from experiment.rsi_v35 import native
from experiment.rsi_v36 import bank


def test_coded_native_separates_eight_block_space():
    motifs = [
        [1, 1, 1],
        [2, 2, 2],
        [3, 3, 3],
        [4, 4, 4],
    ]
    code = coded_native.design_code(motifs, 8)
    assert code is not None
    assert len(code["queries"]) <= coded_native.MAX_CODE_PROBES
    assert len(code["lookup"]) == 4 ** 8


def test_coded_native_solves_consumed_v36_transfer_under_cap():
    tasks = bank.stream(
        bank.DEV_SEEDS[0],
        native.DOMAINS[0],
        epochs=4,
        tasks_per_epoch=4,
    )
    motifs = {}
    for task in tasks:
        if task["epoch"] >= 3:
            break
        result = coded_native.acquire(task, isolated=False)
        assert result["solved"]
        assert len(result["calls"]) <= coded_native.MAX_CALLS
        if task["epoch"] == 2:
            ops = result["genome"]["ops"]
            motifs.setdefault(tuple(ops), list(ops))

    known = [motifs[key] for key in sorted(motifs)]
    assert len(known) == 4
    transfer = next(task for task in tasks if task["epoch"] == 3)
    code = coded_native.design_code(known, transfer["slots"] // bank.BLOCK)
    assert code is not None
    result = coded_native.solve(transfer, known, code, isolated=False)
    assert result["solved"]
    assert len(result["calls"]) <= coded_native.MAX_CALLS
