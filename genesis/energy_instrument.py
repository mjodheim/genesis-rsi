"""External E1 energy-instrument evidence contract.

The mutable lineage never owns this interface. A joule observation is admissible
only when a real external instrument provides identity, provenance and explicit
measurement boundaries. This module performs validation only; it never estimates
energy from CPU time, latency, node counts or hardware TDP.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping, Protocol, runtime_checkable


class EnergyInstrumentError(ValueError):
    """Raised when direct-energy evidence is incomplete or non-physical."""


@dataclass(frozen=True)
class EnergyObservation:
    energy_joules: float
    instrument_id: str
    instrument_method: str
    provenance: str
    interval_start_ns: int
    interval_end_ns: int
    baseline_treatment: str

    def __post_init__(self) -> None:
        if not isfinite(self.energy_joules) or self.energy_joules < 0:
            raise EnergyInstrumentError("energy_joules must be a finite direct observation")
        for value, label in (
            (self.instrument_id, "instrument identity"),
            (self.instrument_method, "instrument method"),
            (self.provenance, "instrument provenance"),
            (self.baseline_treatment, "baseline treatment"),
        ):
            if not value.strip():
                raise EnergyInstrumentError(f"{label} is required")
        if self.interval_start_ns < 0 or self.interval_end_ns <= self.interval_start_ns:
            raise EnergyInstrumentError("measurement interval boundaries are invalid")

    def record(self) -> dict[str, object]:
        return {
            "energy_joules": self.energy_joules,
            "instrument_id": self.instrument_id,
            "instrument_method": self.instrument_method,
            "provenance": self.provenance,
            "interval_start_ns": self.interval_start_ns,
            "interval_end_ns": self.interval_end_ns,
            "baseline_treatment": self.baseline_treatment,
        }


@runtime_checkable
class EnergyInstrument(Protocol):
    """External adapter for a real energy measurement instrument."""

    @property
    def identity(self) -> Mapping[str, str]:
        ...

    def measure(self) -> EnergyObservation:
        ...


def require_real_observation(observation: EnergyObservation | None) -> EnergyObservation:
    """Fail closed: absence of a real observation remains missing energy."""
    if observation is None:
        raise EnergyInstrumentError("energy is unavailable without a real instrument observation")
    if not isinstance(observation, EnergyObservation):
        raise EnergyInstrumentError("unrecognized energy observation type")
    return observation
