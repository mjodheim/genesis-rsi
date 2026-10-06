"""Compatibility alias for :mod:`genesis.operators.structural`."""

import sys as _sys
from genesis.operators import structural as _canonical

_sys.modules[__name__] = _canonical
