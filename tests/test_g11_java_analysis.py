import tempfile
import unittest
from pathlib import Path
from genesis.java_analysis import analyze

JDK = Path('/home/anthony/tools/jdk11/bin')

@unittest.skipUnless((JDK / 'javac').exists(), 'JDK11 unavailable')
class JavaAnalysisTests(unittest.TestCase):
    def test_methods_branches_and_calls(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / 'Example.java'
            src.write_text('class Example { String clean(String x) { if (x == null) return null; return x.trim(); } }')
            result = analyze(src, java=JDK/'java', javac=JDK/'javac')
            kinds = {n['kind'] for n in result['nodes']}
            self.assertTrue({'CLASS', 'METHOD', 'IF', 'METHOD_INVOCATION'}.issubset(kinds))
            self.assertTrue(any(n['name'] == 'clean' for n in result['nodes']))
            self.assertTrue(all(0 <= n['start'] <= n['end'] <= len(src.read_text()) for n in result['nodes']))
            self.assertEqual(result['schema'], 'genesis-java-understanding-v2')
