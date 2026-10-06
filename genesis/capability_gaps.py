"""Compatibility alias for :mod:`genesis.learning.capability_gaps`."""

import sys as _sys
from genesis.learning import capability_gaps as _canonical

_sys.modules[__name__] = _canonical
