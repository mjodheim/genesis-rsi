from genesis import failure_attribution as attribution
from genesis.failure_attribution import Condition


def _cases():
    rows = []
    rows += [{"located": True, "built": True, "won": True}] * 8
    rows += [{"located": True, "built": True, "won": False}] * 1
    rows += [{"located": True, "built": False, "won": False}] * 1
    rows += [{"located": False, "built": True, "won": True}] * 4
    rows += [{"located": False, "built": False, "won": False}] * 6
    return rows


CONDITIONS = (Condition("located", "localizer", lambda case: case["located"]),
              Condition("built", "proposer", lambda case: case["built"]))


def test_a_later_condition_is_judged_only_where_the_earlier_ones_hold():
    report = attribution.attribute(_cases(), CONDITIONS, lambda case: case["won"])
    located, built = report["conditions"]
    assert (located["met"], located["succeeded_when_met"], located["unmet"], located["succeeded_when_unmet"]) == (10, 8, 10, 4)
    assert located["estimated_gain_if_always_met"] == 4.0
    assert built["cases_where_earlier_conditions_hold"] == 10
    assert (built["met"], built["unmet"]) == (9, 1)
    assert built["estimated_gain_if_always_met"] == round(8 / 9, 2)
    assert report["limiting_component"] == "localizer"
    assert report["failures_by_first_unmet_condition"] == {"located": 6, "built": 1, "every condition met": 1}


def test_no_component_is_named_when_nothing_separates_success_from_failure():
    cases = [{"located": True, "built": True, "won": True}] * 3
    report = attribution.attribute(cases, CONDITIONS, lambda case: case["won"])
    assert report["limiting_component"] is None
    assert [row["estimated_gain_if_always_met"] for row in report["conditions"]] == [0.0, 0.0]


def test_a_condition_never_met_has_no_estimate():
    cases = [{"located": False, "built": True, "won": False}] * 2
    report = attribution.attribute(cases, CONDITIONS, lambda case: case["won"])
    assert report["conditions"][0]["estimated_gain_if_always_met"] is None


def test_the_estimate_states_what_a_change_should_gain():
    report = attribution.attribute(_cases(), CONDITIONS, lambda case: case["won"])
    assert attribution.predicted_gain(report["conditions"][0], 5) == 2.0


def test_repair_records_are_read_per_arm():
    result = {"cases": [
        {"case": "A-1", "usable": True, "fix_covered": {"x": True}, "arms": {"x": {
            "solved": True, "verdicts": [{"stopped_at": "passed"}]}}},
        {"case": "A-2", "usable": True, "fix_covered": {"x": False}, "arms": {"x": {
            "solved": False, "verdicts": [{"stopped_at": "compile"}]}}},
        {"case": "A-3", "usable": False, "fix_covered": {"x": False}, "arms": {"x": {"solved": False, "verdicts": []}}},
    ]}
    report = attribution.repair_attribution(result, "x")
    assert report["cases"] == 2 and report["succeeded"] == 1
    assert report["failures_by_first_unmet_condition"] == {"the evidence covers the place of the fix": 1}
