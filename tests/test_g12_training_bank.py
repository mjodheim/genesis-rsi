"""Safe provenance for a merged training bank; not an independent RSI gate."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import unittest

from genesis.g12_training_bank import validate_training_bank
from genesis.learning import self_extension
from genesis.trust_root import digest_of

FILE=Path(__file__).resolve().parents[1]/"experiment/g12/G12_TRAINING_OPERATOR_BANK_20261008.json"


class G12OperatorBankTests(unittest.TestCase):
    def setUp(self):
        self.bank=json.loads(FILE.read_text())

    def test_two_real_development_operators_are_persisted_with_provenance(self):
        bank=validate_training_bank(self.bank)
        self.assertEqual(bank["released_training_rounds"],2)
        self.assertEqual(bank["learned_operator_count"],2)
        self.assertEqual(bank["new_independent_full_suite_successes"],0)
        self.assertTrue(bank["merged_seed_is_not_a_continuation_of_source_lineages"])
        self.assertTrue(bank["operator_semantics_preexisting_human_authored_generators"])
        self.assertEqual(len({x["receipt_digest"] for x in bank["sources"]}),2)
        self.assertEqual(len({
            digest for item in bank["sources"]
            for digest in item["acquired_operator_digests"]
        }),2)
        memory=self_extension.validate_memory(bank["retained_memory"])
        self.assertEqual(memory["generation"],0)
        self.assertEqual(len(memory["operators"]),2)

    def test_tampered_operator_bank_rejected(self):
        bank=copy.deepcopy(self.bank)
        bank["new_independent_full_suite_successes"]=1
        with self.assertRaisesRegex(ValueError,"bank digest"):
            validate_training_bank(bank)
        bank["bank_digest"]=digest_of({k:v for k,v in bank.items() if k!="bank_digest"})
        with self.assertRaisesRegex(ValueError,"scope"):
            validate_training_bank(bank)

    def test_malicious_operator_digest_does_not_pass_hash_chain(self):
        bank=copy.deepcopy(self.bank)
        bank["retained_memory"]["operators"][0]["source_result_digest"]="bad"
        bank["bank_digest"]=digest_of({k:v for k,v in bank.items() if k!="bank_digest"})
        with self.assertRaisesRegex(ValueError,"digest"):
            validate_training_bank(bank)


if __name__=="__main__":
    unittest.main()
