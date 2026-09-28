from __future__ import annotations

import pytest
from genesis.energy_measurement import EnergyMeasurementError, create_resource_measurement

BASE = {
    "subject_digest": "subject-v1",
    "evaluator_digest": "evaluator-v1",
    "case_set_digest": "cases-v1",
    "budget_digest": "budget-v1",
    "hardware_identity": {"device": "cpu-0", "machine": "host-a"},
    "runtime_identity": {"python": "3.11", "os": "linux"},
    "measurement_provenance": {"collector": "e0-local-v1"},
    "case_results": [{"case_digest": "case-a", "passed": True, "node_executions": 2}],
    "cpu_process_time_ns": 100,
    "wall_latency_ns": 150,
    "peak_memory_bytes": 4096,
}

def test_e0_keeps_dimensions_separate_and_energy_missing():
    record = create_resource_measurement(**BASE)
    assert record["capability"] == {"passed": 1, "evaluated": 1}
    assert record["resources"]["cpu_process_time_ns"] == 100
    assert record["resources"]["cpu_time_is_compute_proxy"] is True
    assert record["resources"]["wall_latency_ns"] == 150
    assert record["resources"]["peak_memory_bytes"] == 4096
    assert record["resources"]["energy_joules"] is None
    assert record["resources"]["energy_measurement_available"] is False

def test_e0_requires_measurement_context():
    for field in ("hardware_identity", "runtime_identity", "measurement_provenance"):
        args = dict(BASE)
        args[field] = {}
        with pytest.raises(EnergyMeasurementError, match="required"):
            create_resource_measurement(**args)

def test_e1_joules_require_instrument_identity():
    with pytest.raises(EnergyMeasurementError, match="instrument"):
        create_resource_measurement(**BASE, energy_joules=1.25)
    record = create_resource_measurement(
        **BASE, energy_joules=1.25,
        energy_instrument={"kind": "power-meter", "serial": "meter-001", "method": "direct"},
    )
    assert record["resources"]["energy_measurement_available"] is True
    assert record["resources"]["energy_joules"] == 1.25

def test_instrument_without_joules_is_not_an_energy_measurement():
    with pytest.raises(EnergyMeasurementError, match="instrument"):
        create_resource_measurement(
            **BASE, energy_instrument={"kind": "power-meter", "serial": "meter-001"}
        )
