"""V2 genome affects actual candidate order without altering the project."""
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import unittest

from genesis import repair_strategist
from genesis.v2.genome import make_seed, mutate
from genesis.v2.live_adapter import rerank, observable_features
from tests.test_java_state_consistency_mutations import synthetic


class LiveV2AdapterTests(unittest.TestCase):
    def test_opt_in_only_and_byte_identical_candidate_set(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            files=[]
            for name in ("Voucher", "Parcel"):
                source=root/(name+".java")
                source.write_text(synthetic(name, "label"))
                files.append(name+".java")
            before={p:(root/p).read_bytes() for p in files}
            arguments={
                "include_prefixes":files,"focus_paths":files,
                "max_candidates":60,"per_family_budget":60,
            }
            original=repair_strategist.generate(root,**arguments)
            seed=repair_strategist.generate(root,**arguments,
                                            v2_discovery_genome=make_seed())
            self.assertNotIn("v2_discovery_ranking",original)
            self.assertEqual(
                [x["candidate_digest"] for x in seed["candidates"]],
                [x["candidate_digest"] for x in original["candidates"]],
            )
            trained=mutate(make_seed(),"atomic",1)
            reranked=repair_strategist.generate(
                root,**arguments,v2_discovery_genome=trained,
            )
            self.assertEqual(
                sorted((c["path"],hashlib.sha256(c["content_utf8"].encode()).hexdigest())
                       for c in reranked["candidates"]),
                sorted((c["path"],hashlib.sha256(c["content_utf8"].encode()).hexdigest())
                       for c in original["candidates"]),
            )
            self.assertEqual([c["logical_index"] for c in reranked["candidates"]],
                             list(range(reranked["candidate_count"])))
            self.assertTrue(reranked["v2_discovery_ranking"]["candidate_set_unchanged"])
            self.assertTrue(reranked["v2_discovery_ranking"]["policy_not_deployed_or_promoted"])
            self.assertEqual({p:(root/p).read_bytes() for p in files},before)
            self.assertEqual(original["strategy_digest"],
                             repair_strategist.generate(root,**arguments)["strategy_digest"])

    def test_genome_cannot_override_trusted_preflight_and_reserved_slot(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            path=root/"Voucher.java"
            path.write_text(synthetic())
            options={
                "include_prefixes":["Voucher.java"],
                "focus_paths":["Voucher.java"], "max_candidates":8,
                "v2_discovery_genome":make_seed(),
            }
            with self.assertRaisesRegex(ValueError,"cannot override"):
                repair_strategist.generate(root,**options,
                    compile_preflight_javac=Path("/does/not/exist"))
            with self.assertRaisesRegex(ValueError,"cannot override"):
                repair_strategist.generate(root,**options,g12_retained_probe_slots=1)

    def test_invalid_ungrounded_feature_is_never_a_rank(self):
        with self.assertRaises((ValueError,KeyError)):
            rerank([{"path":"A.java","plan":{"depth":1,"component_operators":[]},
                     "content_utf8":"class A {}","candidate_digest":"a"*64}],
                   {"weights":{"other":1},"schema":"bad"})

if __name__=="__main__":
    unittest.main()
