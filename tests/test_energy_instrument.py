from __future__ import annotations

import math
import pytest
from genesis.energy_instrument import EnergyInstrumentError, EnergyObservation, require_real_observation

def valid(**changes):
    values = dict(energy_joules=12.5, instrument_id="rapl-package-0", instrument_method="sysfs-energy-counter", provenance="host-cpu-package-0", interval_start_ns=100, interval_end_ns=200, baseline_treatment="raw interval; no idle subtraction")
    values.update(changes)
    return EnergyObservation(**values)

def test_observation_preserves_direct_measurement_provenance():
    observation = valid()
    assert observation.record()["energy_joules"] == 12.5
    assert observation.record()["instrument_id"] == "rapl-package-0"

@pytest.mark.parametrize("value", [-1.0, math.inf, math.nan])
def test_nonphysical_energy_fails_closed(value):
    with pytest.raises(EnergyInstrumentError):
        valid(energy_joules=value)

@pytest.mark.parametrize("field", ["instrument_id", "instrument_method", "provenance", "baseline_treatment"])
def test_missing_provenance_fails_closed(field):
    with pytest.raises(EnergyInstrumentError):
        valid(**{field: " "})

def test_invalid_interval_fails_closed():
    with pytest.raises(EnergyInstrumentError):
        valid(interval_start_ns=200, interval_end_ns=200)

def test_missing_real_instrument_observation_stays_missing():
    with pytest.raises(EnergyInstrumentError):
        require_real_observation(None)
