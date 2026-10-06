"""Compatibility alias for :mod:`genesis.languages.toolchains`."""

import sys as _sys
from genesis.languages import toolchains as _canonical

_sys.modules[__name__] = _canonical
