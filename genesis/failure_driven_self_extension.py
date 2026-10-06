"""Compatibility alias for :mod:`genesis.learning.self_extension`."""

import sys as _sys
from genesis.learning import self_extension as _canonical

_sys.modules[__name__] = _canonical
