"""External energy-instrument boundary for the Energy/Compute Frontier.

E0 compatibility is preserved while E1 adds a stricter typed adapter contract.
No function in this module estimates joules from CPU time, latency, node counts,
TDP, or another proxy.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, runtime_checkable


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
        if isinstance(self.energy_joules, bool) or not isinstance(self.energy_joules, (int, float)):
            raise EnergyInstrumentError("direct energy observation must be numeric")
        if not math.isfinite(float(self.energy_joules)) or self.energy_joules < 0:
            raise EnergyInstrumentError("direct energy observation must be finite and non-negative")
        if not isinstance(self.instrument_identity, Mapping) or not self.instrument_identity:
            raise EnergyInstrumentError("real instrument identity and provenance are required")
        required = (self.measurement_method, self.interval_start, self.interval_end, self.baseline_treatment)
        if any(not isinstance(value, str) or not value.strip() for value in required):
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
    return EnergyInstrumentObservation(
        energy_joules=energy_joules,
        instrument_identity=instrument_identity,
        measurement_method=measurement_method,
        interval_start=interval_start,
        interval_end=interval_end,
        baseline_treatment=baseline_treatment,
    )


def validate_energy_provenance(provenance: Mapping[str, Any]) -> None:
    if not isinstance(provenance, Mapping) or not provenance:
        raise EnergyInstrumentError("real instrument identity and provenance are required")
    required = ("measurement_method", "interval_start", "interval_end", "baseline_treatment")
    if any(not isinstance(provenance.get(name), str) or not str(provenance.get(name)).strip() for name in required):
        raise EnergyInstrumentError("method, interval boundaries and baseline treatment are required")


@dataclass(frozen=True)
class EnergyObservation:
    """Stricter E1 observation emitted by an external real-instrument adapter."""
    energy_joules: float
    instrument_id: str
    instrument_method: str
    provenance: str
    interval_start_ns: int
    interval_end_ns: int
    baseline_treatment: str

    def __post_init__(self) -> None:
        if isinstance(self.energy_joules, bool) or not isinstance(self.energy_joules, (int, float)):
            raise EnergyInstrumentError("energy_joules must be a numeric direct observation")
        if not math.isfinite(float(self.energy_joules)) or self.energy_joules < 0:
            raise EnergyInstrumentError("energy_joules must be a finite direct observation")
        for value, label in (
            (self.instrument_id, "instrument identity"),
            (self.instrument_method, "instrument method"),
            (self.provenance, "instrument provenance"),
            (self.baseline_treatment, "baseline treatment"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise EnergyInstrumentError(f"{label} is required")
        if (
            isinstance(self.interval_start_ns, bool)
            or isinstance(self.interval_end_ns, bool)
            or not isinstance(self.interval_start_ns, int)
            or not isinstance(self.interval_end_ns, int)
            or self.interval_start_ns < 0
            or self.interval_end_ns <= self.interval_start_ns
        ):
            raise EnergyInstrumentError("measurement interval boundaries are invalid")

    def record(self) -> dict[str, object]:
        return {
            "energy_joules": float(self.energy_joules),
            "instrument_id": self.instrument_id,
            "instrument_method": self.instrument_method,
            "provenance": self.provenance,
            "interval_start_ns": self.interval_start_ns,
            "interval_end_ns": self.interval_end_ns,
            "baseline_treatment": self.baseline_treatment,
        }


@runtime_checkable
class EnergyInstrument(Protocol):
    @property
    def identity(self) -> Mapping[str, str]:
        ...

    def measure(self) -> EnergyObservation:
        ...


def require_real_observation(observation: EnergyObservation | None) -> EnergyObservation:
    if observation is None:
        raise EnergyInstrumentError("energy is unavailable without a real instrument observation")
    if not isinstance(observation, EnergyObservation):
        raise EnergyInstrumentError("unrecognized energy observation type")
    return observation
