"""External energy-instrument boundary for the Energy/Compute Frontier.

This module records direct observations from a real instrument.  It deliberately does
not estimate joules from CPU time, wall latency, TDP, node counts, or any other proxy.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class EnergyInstrumentError(ValueError):
    pass


@dataclass(frozen=True)
class EnergyInstrumentObservation:
    energy_joules: float
    instrument_identity: Mapping[str, Any]
    measurement_method: str
    interval_start: str
    interval_end: str
    baseline_treatment: str

    def __post_init__(self) -> None:
        if self.energy_joules < 0:
            raise EnergyInstrumentError("direct energy observation cannot be negative")
        if not isinstance(self.instrument_identity, Mapping) or not self.instrument_identity:
            raise EnergyInstrumentError("real instrument identity and provenance are required")
        required = ("measurement_method", "interval_start", "interval_end", "baseline_treatment")
        if any(not getattr(self, name) for name in required):
            raise EnergyInstrumentError("method, interval boundaries and baseline treatment are required")

    def provenance(self) -> dict[str, Any]:
        return {
            **dict(self.instrument_identity),
            "measurement_method": self.measurement_method,
            "interval_start": self.interval_start,
            "interval_end": self.interval_end,
            "baseline_treatment": self.baseline_treatment,
        }


def direct_energy_observation(
    *, energy_joules: float, instrument_identity: Mapping[str, Any],
    measurement_method: str, interval_start: str, interval_end: str,
    baseline_treatment: str,
) -> EnergyInstrumentObservation:
    """Create an E1 observation from an already measured, direct instrument reading."""
    return EnergyInstrumentObservation(
        energy_joules=float(energy_joules),
        instrument_identity=instrument_identity,
        measurement_method=str(measurement_method),
        interval_start=str(interval_start),
        interval_end=str(interval_end),
        baseline_treatment=str(baseline_treatment),
    )
