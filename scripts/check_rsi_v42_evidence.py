"""Require and replay the complete V42 prefix; never execute new tasks."""
import json

from experiment.rsi_v25.commitments import digest
from experiment.rsi_v33 import storage
from experiment.rsi_v42 import campaign


def check():
    # Do not use campaign.check()'s optional/incomplete development default in CI.
    computed = campaign.check(require_prefix=True, replay=True)
    stored = storage.read_json(campaign.DIRECTORY / "PREFIX_REPORT.json")
    if digest(stored) != digest(computed):
        raise ValueError("V42 prefix report differs from the complete replayed evidence")
    if (computed["l9_open_ended_passed"] is not False
            or computed["l10_independent_passed"] is not False
            or computed["finite_prefix_cannot_establish_open_endedness"] is not True):
        raise ValueError("A finite V42 prefix cannot establish open-ended L9 or independent L10")
    return computed


if __name__ == "__main__":
    report = check()
    print(json.dumps({key: value for key, value in report.items()
                      if key != "epoch_verdicts"}, indent=2))
