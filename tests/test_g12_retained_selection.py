"""G12 retained A6c operators get bounded, opt-in candidate exploration."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from genesis import repair_strategist, java_state_consistency_mutations
from genesis.learning import self_extension
from genesis.operators import structural as structural_operators
from tests.test_g12_operator_lab import source


class RetainedPriorityTests(unittest.TestCase):
    def _setting(self):
        context=TemporaryDirectory()
        root=Path(context.name)
        file=root/"Voucher.java"
        before=source()
        file.write_text(before)
        emitted=java_state_consistency_mutations.generate(
            root,include_prefixes=["Voucher.java"]
        )
        after=emitted["candidates"][0]["content_utf8"]
        operator=structural_operators.synthesize_operator(
            before, after, source_result_digest="a"*64,
            source_path="Voucher.java", context_lines=0,
        )
        memory=self_extension.create_memory(operators=[operator])
        kwargs={
            "focus_paths":["Voucher.java"],"include_prefixes":["Voucher.java"],
            "max_candidates":40,"per_family_budget":40,
            "composition_fraction":0.4,
            "retained_memory":memory,
            "atomic_first_experimental":True,
        }
        return context,root,kwargs,after

    def test_validated_retained_operator_is_not_lost_at_deduplication(self):
        context,root,opts,after=self._setting()
        with context:
            baseline=repair_strategist.generate(root,**opts)
            chosen=repair_strategist.generate(
                root,**opts,g12_retained_probe_slots=1
            )
            self.assertNotIn("g12_retained_probe",baseline)
            self.assertEqual(
                chosen["candidates"][0]["plan"]["component_operators"],
                ["retained_structural_operator"],
            )
            self.assertEqual(chosen["candidates"][0]["content_utf8"],after)
            self.assertEqual(chosen["g12_retained_probe"]["selected_slots"],1)
            self.assertEqual(chosen["g12_retained_probe"]["requested_slots"],1)
            self.assertFalse(chosen["g12_retained_probe"]["promotion_does_not_prove_repair"] is False)
            self.assertEqual(
                baseline["strategy_digest"],
                repair_strategist.generate(root,**opts)["strategy_digest"],
            )

    def test_retained_probe_rejects_invalid_configurations(self):
        context,root,opts,after=self._setting()
        with context:
            for slots in (-1,5,True):
                with self.subTest(slots=slots),self.assertRaisesRegex(ValueError,"slots"):
                    repair_strategist.generate(root,**opts,g12_retained_probe_slots=slots)
            missing=dict(opts)
            missing["retained_memory"]=None
            with self.assertRaisesRegex(ValueError,"require retained training memory"):
                repair_strategist.generate(root,**missing,g12_retained_probe_slots=1)

    def test_no_retained_candidate_is_not_a_false_success(self):
        context,root,opts,after=self._setting()
        with context:
            empty=self_extension.empty_memory()
            result=repair_strategist.generate(root,
                **{**opts,"retained_memory":empty},
                g12_retained_probe_slots=1,
            )
            self.assertEqual(result["g12_retained_probe"]["selected_slots"],0)
            self.assertTrue(result["g12_retained_probe"]["promotion_does_not_prove_repair"])


if __name__=="__main__":
    unittest.main()
