"""Compatibility alias for :mod:`genesis.runtime.candidate_scheduler`."""

import sys as _sys
from genesis.runtime import candidate_scheduler as _canonical

_sys.modules[__name__] = _canonical
