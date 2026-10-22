"""The slow historical CIRCUIT2 probe must be opt-in, not run on import."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


class Circuit2ImportHygiene(unittest.TestCase):
    def test_import_does_not_execute_expensive_benchmark(self):
        snippet = """import importlib, sys
from unittest.mock import patch
sys.path.insert(0, 'scripts')
from genesis import circuit_engine
with patch.object(circuit_engine, 'attempt', side_effect=RuntimeError('benchmark unexpectedly ran')):
    module = importlib.import_module('run_circuit2_leverage_probe')
    assert callable(module.main)
"""
        result = subprocess.run(
            [sys.executable, "-B", "-c", snippet], cwd=ROOT,
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '')

    def test_explicit_main_preserves_all_probe_combinations(self):
        sys.path.insert(0, str(SCRIPTS))
        import run_circuit2_leverage_probe as probe
        with (patch.object(probe, 'lineage', return_value=(1, 2, 3, [4])) as lineage,
              patch.object(probe.t, 'circuit2_suite', return_value=[]),
              patch.object(probe.cp, 'seed_procedure', return_value=object()),
              patch.object(probe.cp, 'mutate', return_value=object()),
              redirect_stdout(io.StringIO()) as output):
            self.assertEqual(probe.main(), 0)
        lines = output.getvalue().splitlines()
        self.assertEqual(len(lines), 9)
        self.assertEqual(lineage.call_count, 99)  # 9 scenarios × (1 fixed + 10 mutants)
        self.assertTrue(any('budget=65536' in line for line in lines))
        self.assertTrue(any('tried=3' in line for line in lines))


if __name__ == '__main__':
    unittest.main()
