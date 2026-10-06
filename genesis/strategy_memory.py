"""Compatibility alias for :mod:`genesis.memory.strategy`."""

import sys as _sys
from genesis.memory import strategy as _canonical

_sys.modules[__name__] = _canonical
