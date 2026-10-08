"""The optional guard transfer integrates in actual repair selection."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from genesis import repair_strategist
from tests.test_java_sibling_guard_mutations import case


class SiblingSelectionTests(unittest.TestCase):
    def test_new_operator_has_to_be_explicitly_enabled(self):
        with TemporaryDirectory() as td:
            base=Path(td)
            sample=base/'Signal.java'
            sample.write_text(case())
            settings=dict(include_prefixes=['Signal.java'],focus_paths=['Signal.java'],
                max_candidates=50,per_family_budget=50,atomic_first_experimental=True)
            baseline=repair_strategist.generate(base,**settings)
            updated=repair_strategist.generate(base,**settings,sibling_guard_experimental=True)
            operator='java_transfer_sibling_invalid_state_guard'
            self.assertFalse(any(operator in r['plan']['component_operators'] for r in baseline['candidates']))
            self.assertTrue(any(operator in r['plan']['component_operators'] for r in updated['candidates']))
            self.assertFalse(baseline.get('g11_sibling_guard_experimental',False))
            self.assertTrue(updated['g11_sibling_guard_experimental'])
            self.assertEqual(updated['family_activation']['java_sibling_guard']['accepted'],1)
            self.assertEqual(baseline['strategy_digest'],
                repair_strategist.generate(base,**settings)['strategy_digest'])
