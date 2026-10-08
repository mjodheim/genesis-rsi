"""G11 detachable read-only security and performance insight modules."""
from .registry import InsightRegistry
from .security import PythonSecurityModule, JavaSecurityModule
from .performance import PythonPerformanceModule, JavaPerformanceModule

__all__ = [
    "InsightRegistry", "PythonSecurityModule", "JavaSecurityModule",
    "PythonPerformanceModule", "JavaPerformanceModule",
]
