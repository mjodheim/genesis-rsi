"""Tests ciblés hors réseau.

Résultat attesté dans cette proposition : aucun test exécuté, conformément à
la consigne sans outils ni exécution. Leur réussite reste à vérifier.
Aucune validation du jalon 2 n'est revendiquée.
"""

import hashlib
import json
import unittest

from genesis.mira_policy_contract import ExternalReceipt, JsonObjectEnvelope

class PolicyContractTests(unittest.TestCase):
    def receipt(self, budget=None):
        return ExternalReceipt.create(
            policy_sha256=JsonObjectEnvelope.create({"policy": "revue"}).sha256,
            task_id="task-1",
            judge_id="external-1",
            declared_result={"success": False, "reason": "échec", "score": 0},
            consumed_budget=budget if budget is not None else {
                "models": [], "tokens": 0, "proposals": 0, "time_seconds": 0.0,
            },
        )

    def test_key_order_and_utf8(self):
        first = JsonObjectEnvelope.create({"z": {"b": 2, "a": 1}, "a": "é"})
        second = JsonObjectEnvelope.create({"a": "é", "z": {"a": 1, "b": 2}})
        self.assertEqual(first, second)
        self.assertEqual(
            first.canonical_utf8, '{"a":"é","z":{"a":1,"b":2}}'.encode("utf-8"),
        )
        self.assertEqual(
            first.sha256, hashlib.sha256(first.canonical_utf8).hexdigest(),
        )

    def test_content_changes_digest(self):
        self.assertNotEqual(
            JsonObjectEnvelope.create({"value": 1}).sha256,
            JsonObjectEnvelope.create({"value": 2}).sha256,
        )

    def test_round_trip_and_detached_payload(self):
        source = {"nested": [{"value": 1}]}
        envelope = JsonObjectEnvelope.create(source)
        source["nested"][0]["value"] = 2
        exposed = envelope.payload
        exposed["nested"].clear()
        restored = JsonObjectEnvelope.from_dict(
            json.loads(json.dumps(envelope.to_dict(), allow_nan=False)),
        )
        self.assertEqual(restored, envelope)
        self.assertEqual(restored.payload, {"nested": [{"value": 1}]})

    def test_unknown_versions(self):
        for version in (0, 2, "1", True, None):
            with self.subTest(version=version):
                data = JsonObjectEnvelope.create({}).to_dict()
                data["version"] = version
                with self.assertRaises(ValueError):
                    JsonObjectEnvelope.from_dict(data)
                data = self.receipt().to_dict()
                data["version"] = version
                with self.assertRaises(ValueError):
                    ExternalReceipt.from_dict(data)
                data = self.receipt().to_dict()
                data["envelope"]["version"] = version
                with self.assertRaises(ValueError):
                    ExternalReceipt.from_dict(data)

    def test_nested_non_finite_values(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    JsonObjectEnvelope.create({"nested": [{"number": value}]})
                with self.assertRaises(ValueError):
                    self.receipt({
                        "models": [], "tokens": 0, "proposals": 0,
                        "time_seconds": value,
                    })

    def test_non_json_values(self):
        for payload in ({1: "key"}, {"value": (1,)}, {"value": {1}}, []):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    JsonObjectEnvelope.create(payload)

    def test_digest_and_representation_tampering(self):
        original = JsonObjectEnvelope.create({"value": 1})
        for field, value in (
            ("sha256", "0" * 64),
            ("sha256", "invalid"),
            ("payload", {"value": 2}),
            ("canonical_utf8", '{"value":2}'),
            ("canonical_utf8", '{ "value": 1 }'),
        ):
            with self.subTest(field=field, value=value):
                data = original.to_dict()
                data[field] = value
                with self.assertRaises(ValueError):
                    JsonObjectEnvelope.from_dict(data)
        data = self.receipt().to_dict()
        data["envelope"]["payload"]["policy_sha256"] = "f" * 64
        with self.assertRaises(ValueError):
            ExternalReceipt.from_dict(data)

    def test_failure_and_exact_budget_round_trip(self):
        for budget in (
            {"models": [], "tokens": 0, "proposals": 0, "time_seconds": 0.0},
            {"models": ["model-a", "model-a"], "tokens": 12,
             "proposals": 3, "time_seconds": 1.25},
            {"models": ["model-b"], "tokens": 0,
             "proposals": 0, "time_seconds": 0},
        ):
            with self.subTest(budget=budget):
                receipt = self.receipt(budget)
                restored = ExternalReceipt.from_dict(
                    json.loads(json.dumps(receipt.to_dict(), allow_nan=False)),
                )
                self.assertEqual(restored, receipt)
                self.assertEqual(restored.payload["consumed_budget"], budget)
                self.assertIs(
                    type(restored.payload["consumed_budget"]["time_seconds"]),
                    type(budget["time_seconds"]),
                )
                self.assertEqual(restored.payload["declared_result"], {
                    "success": False, "reason": "échec", "score": 0,
                })
                self.assertIs(restored.payload["declared_result"]["success"], False)
                self.assertEqual(restored.payload["task_id"], "task-1")
                self.assertEqual(restored.payload["judge_id"], "external-1")
                self.assertEqual(
                    restored.payload["policy_sha256"], receipt.payload["policy_sha256"],
                )
