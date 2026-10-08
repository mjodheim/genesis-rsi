"""V2.1 grammar is optional; structural witnesses are not success labels."""
from pathlib import Path
from tempfile import TemporaryDirectory
from hashlib import sha256
import unittest

from genesis import repair_strategist
from genesis.v2.semantic_adapter import generate as candidate_generate
from genesis.v2.genome import mutate, make_seed
from tests.test_v21_semantic_dsl import fixture, oracle


class V21PlannerTests(unittest.TestCase):
    def test_real_strategist_opt_in_and_default_intact(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            filename="Signal.java"
            before=fixture()
            (root/filename).write_text(before)
            kwargs=dict(
                include_prefixes=[filename],focus_paths=[filename],
                max_candidates=48,per_family_budget=48,
                atomic_first_experimental=True,
            )
            baseline=repair_strategist.generate(root,**kwargs)
            optin=repair_strategist.generate(
                root,**kwargs,v21_semantic_hypotheses_experimental=True
            )
            self.assertNotIn("v21_semantic_hypothesis_generation",baseline)
            self.assertEqual(optin["family_activation"]["v21_peer_contract"]["accepted"],1)
            self.assertEqual(
                optin["candidates"][0]["plan"]["component_operators"],
                ["v21_peer_contract_hypothesis"],
            )
            self.assertTrue(optin["v21_semantic_hypothesis_generation"]["only_buggy_source_facts"])
            self.assertIn("if (corrupt || peer.corrupt)",optin["candidates"][0]["content_utf8"])
            self.assertEqual((root/filename).read_text(),before)
            self.assertEqual(
                repair_strategist.generate(root,**kwargs)["strategy_digest"],
                baseline["strategy_digest"],
            )

    def test_v21_with_evolving_v2_rank_policy_remains_source_only(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"Signal.java").write_text(fixture())
            descendant=mutate(make_seed(),"atomic",1)
            results=repair_strategist.generate(
                root,include_prefixes=["Signal.java"],focus_paths=["Signal.java"],
                max_candidates=48,per_family_budget=48,
                v2_discovery_genome=descendant,
                v21_semantic_hypotheses_experimental=True,
            )
            self.assertTrue(results["v2_discovery_ranking"]["candidate_set_unchanged"])
            self.assertEqual(results["family_activation"]["v21_peer_contract"]["accepted"],1)
            self.assertEqual(results["v2_discovery_ranking"]["genome_digest"],descendant["genome_digest"])

    def test_bounded_adapter_refuses_directory_and_unknown_paths(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"Signal.java").write_text(fixture())
            for inputs in ((),("src/main/java",),("../Signal.java",)):
                with self.subTest(inputs=inputs),self.assertRaises((ValueError,FileNotFoundError)):
                    candidate_generate(root,include_prefixes=inputs)
            with self.assertRaises(ValueError):
                candidate_generate(root,include_prefixes=["Signal.java"],max_candidates=0)

if __name__=="__main__":
    unittest.main()
