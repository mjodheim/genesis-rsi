"""Compatibility alias for :mod:`genesis.languages.native_diagnosis`."""

import sys as _sys
from genesis.languages import native_diagnosis as _canonical

_sys.modules[__name__] = _canonical
