"""Tests hors réseau de la sérialisation canonique et des reçus déclaratifs."""

import copy
import hashlib
import json
import sys
import unittest

from genesis.mira_policy_contract import (
    BankExternalReceipt,
    CodingPolicy,
    ExternalReceipt,
    JsonObjectEnvelope,
    canonical_json_utf8,
    validate_policy_receipt_consistency,
    validate_receipt_consistency,
)

class CodingPolicyTests(unittest.TestCase):
    """Synthetic offline cases; no test execution is attested by this patch."""

    def fields(self):
        return {
            "localization": "Lire les fichiers et localiser le défaut",
            "tool_order": ["search", "read", "test"],
            "trial_and_repair_strategy": "Essai ciblé puis réparation",
            "task_budget": {
                "models": ["model-a", "model-a"], "tokens": 12,
                "proposals": 3, "time_seconds": 1.25,
            },
        }

    def restore_payload(self, payload):
        return CodingPolicy.from_dict({
            "version": 1,
            "envelope": JsonObjectEnvelope.create(payload).to_dict(),
        })

    def test_round_trip_and_fingerprint(self):
        fields = self.fields()
        policy = CodingPolicy.create(**fields)
        restored = CodingPolicy.from_dict(
            json.loads(json.dumps(policy.to_dict(), allow_nan=False)),
        )
        self.assertEqual(restored, policy)
        self.assertEqual(restored.payload, fields)
        self.assertEqual(policy.sha256, policy.envelope.sha256)
        self.assertEqual(
            policy.sha256,
            hashlib.sha256(policy.envelope.canonical_utf8).hexdigest(),
        )
        reordered = dict(reversed(list(fields.items())))
        reordered["task_budget"] = dict(
            reversed(list(fields["task_budget"].items())),
        )
        self.assertEqual(self.restore_payload(reordered), policy)
        for field, value in (
            ("localization", "Autre localisation"),
            ("tool_order", ["read", "search", "test"]),
            ("trial_and_repair_strategy", "Autre stratégie"),
            ("task_budget", dict(fields["task_budget"], tokens=13)),
        ):
            with self.subTest(field=field):
                changed = dict(fields, **{field: value})
                self.assertNotEqual(
                    CodingPolicy.create(**changed).sha256, policy.sha256,
                )

    def test_mutation_isolation(self):
        fields = self.fields()
        policy = CodingPolicy.create(**fields)
        expected = self.fields()
        fields["tool_order"].clear()
        fields["task_budget"]["models"].clear()
        exposed = policy.payload
        exposed["task_budget"]["tokens"] = 999
        exposed["tool_order"].append("extra")
        data = policy.to_dict()
        restored = CodingPolicy.from_dict(data)
        data["envelope"]["payload"]["task_budget"]["models"].clear()
        self.assertEqual(policy.payload, expected)
        self.assertEqual(restored.payload, expected)
        self.assertEqual(restored, policy)

    def test_missing_and_extra_fields(self):
        original = self.fields()
        for field in original:
            payload = dict(original)
            del payload[field]
            with self.subTest(missing=field), self.assertRaises(ValueError):
                self.restore_payload(payload)
        with self.assertRaises(ValueError):
            self.restore_payload(dict(original, extra=None))
        original = CodingPolicy.create(**original).to_dict()
        for field in original:
            data = dict(original)
            del data[field]
            with self.subTest(missing=field), self.assertRaises(ValueError):
                CodingPolicy.from_dict(data)
        with self.assertRaises(ValueError):
            CodingPolicy.from_dict(dict(original, extra=None))

    def test_invalid_policy_types(self):
        invalid = {
            "localization": ("", None, True, 1, [], {}),
            "trial_and_repair_strategy": ("", None, True, 1, [], {}),
            "tool_order": (None, True, 1, "read", {}, [None], [1], [""]),
            "task_budget": (None, True, 1, "", []),
        }
        for field, values in invalid.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    fields = dict(self.fields(), **{field: value})
                    with self.assertRaises(ValueError):
                        CodingPolicy.create(**fields)
        for value in (None, True, 1, "", []):
            with self.subTest(container=value), self.assertRaises(ValueError):
                CodingPolicy.from_dict(value)
            with self.assertRaises(ValueError):
                CodingPolicy(1, value)

    def test_invalid_budgets(self):
        invalid = {
            "models": (None, True, 0, "model-a", {}, [None], [True], [1]),
            "tokens": (None, True, False, -1, -0.5, 1.0, "", [], {}),
            "proposals": (None, True, False, -1, -0.5, 1.0, "", [], {}),
            "time_seconds": (None, True, False, -1, -0.5, "", [], {}),
        }
        for field, values in invalid.items():
            for value in values + (float("nan"), float("inf"), -float("inf")):
                fields = self.fields()
                fields["task_budget"][field] = value
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValueError):
                        CodingPolicy.create(**fields)
            fields = self.fields()
            del fields["task_budget"][field]
            with self.assertRaises(ValueError):
                CodingPolicy.create(**fields)
        fields = self.fields()
        fields["task_budget"]["extra"] = 0
        with self.assertRaises(ValueError):
            CodingPolicy.create(**fields)

    def test_tampered_envelope_and_versions(self):
        for field, value in (
            ("sha256", "0" * 64), ("version", 2),
            ("payload", {}), ("canonical_utf8", "{}"),
        ):
            data = CodingPolicy.create(**self.fields()).to_dict()
            data["envelope"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                CodingPolicy.from_dict(data)
            policy = CodingPolicy.create(**self.fields())
            if field != "payload":
                object.__setattr__(policy.envelope, field, value)
                with self.assertRaises(ValueError):
                    CodingPolicy(policy.version, policy.envelope)
        for version in (0, 2, True, "1", None):
            data = CodingPolicy.create(**self.fields()).to_dict()
            data["version"] = version
            with self.subTest(version=version), self.assertRaises(ValueError):
                CodingPolicy.from_dict(data)

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

    def test_cyclic_dictionary(self):
        payload = {}
        payload["self"] = payload
        with self.assertRaises(ValueError):
            canonical_json_utf8(payload)

    def test_excessively_deep_structure(self):
        payload = {}
        current = payload
        for _ in range(sys.getrecursionlimit() + 100):
            nested = {}
            current["nested"] = nested
            current = nested
        with self.assertRaises(ValueError):
            canonical_json_utf8(payload)

    def assert_invalid_receipt_payload(self, payload, message):
        data = {
            "version": 1,
            "envelope": JsonObjectEnvelope.create(payload).to_dict(),
        }
        with self.assertRaisesRegex(ValueError, message):
            ExternalReceipt.from_dict(data)

    def test_receipt_envelope_missing_and_extra_fields(self):
        original = self.receipt().to_dict()
        for field in original:
            with self.subTest(missing=field):
                data = dict(original)
                del data[field]
                with self.assertRaisesRegex(
                    ValueError, "Invalid receipt envelope fields",
                ):
                    ExternalReceipt.from_dict(data)
        data = dict(original, extra=None)
        with self.assertRaisesRegex(ValueError, "Invalid receipt envelope fields"):
            ExternalReceipt.from_dict(data)

    def test_receipt_missing_and_extra_fields(self):
        original = self.receipt().payload
        for field in original:
            with self.subTest(missing=field):
                payload = dict(original)
                del payload[field]
                self.assert_invalid_receipt_payload(payload, "Invalid receipt fields")
        self.assert_invalid_receipt_payload(
            dict(original, extra=None), "Invalid receipt fields",
        )

    def test_budget_missing_and_extra_fields(self):
        original = self.receipt().payload["consumed_budget"]
        for field in original:
            with self.subTest(missing=field):
                payload = self.receipt().payload
                del payload["consumed_budget"][field]
                self.assert_invalid_receipt_payload(payload, "Invalid budget fields")
        payload = self.receipt().payload
        payload["consumed_budget"]["extra"] = None
        self.assert_invalid_receipt_payload(payload, "Invalid budget fields")

    def test_invalid_policy_digest(self):
        for value in (None, True, 123, "", "invalid", "a" * 63,
                      "a" * 65, "A" * 64, "g" * 64):
            with self.subTest(value=value):
                payload = self.receipt().payload
                payload["policy_sha256"] = value
                self.assert_invalid_receipt_payload(payload, "Invalid SHA-256 digest")

    def test_invalid_receipt_identifiers(self):
        for field in ("task_id", "judge_id"):
            for value in ("", None, True, 123, [], {}):
                with self.subTest(field=field, value=value):
                    payload = self.receipt().payload
                    payload[field] = value
                    self.assert_invalid_receipt_payload(
                        payload, "Expected a nonempty identifier",
                    )

    def test_negative_and_boolean_budgets(self):
        for field in ("tokens", "proposals", "time_seconds"):
            for value in (-1, -0.5, True, False):
                with self.subTest(field=field, value=value):
                    payload = self.receipt().payload
                    payload["consumed_budget"][field] = value
                    message = (
                        "Expected nonnegative elapsed seconds"
                        if field == "time_seconds"
                        else "Expected a nonnegative integer budget"
                    )
                    self.assert_invalid_receipt_payload(payload, message)

    def test_invalid_budget_type(self):
        for value in (None, True, 0, "", []):
            with self.subTest(value=value):
                payload = self.receipt().payload
                payload["consumed_budget"] = value
                self.assert_invalid_receipt_payload(payload, "Invalid budget fields")

    def test_invalid_models_type_and_elements(self):
        for value in (None, True, 0, "model-a", {}, [None], [True],
                      [1], [[]], [{}], ["model-a", 1]):
            with self.subTest(value=value):
                payload = self.receipt().payload
                payload["consumed_budget"]["models"] = value
                self.assert_invalid_receipt_payload(
                    payload, "Expected model identifiers",
                )

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

    def test_historical_receipt_revalidates_original_envelope(self):
        for field, value, message in (
            ("sha256", "0" * 64, "Inconsistent SHA-256 digest"),
            ("sha256", "invalid", "Invalid SHA-256 digest"),
            ("version", 2, "Unknown contract version"),
            ("version", True, "Unknown contract version"),
        ):
            with self.subTest(field=field, value=value):
                receipt = self.receipt()
                object.__setattr__(receipt.envelope, field, value)
                with self.assertRaisesRegex(ValueError, message):
                    ExternalReceipt(receipt.version, receipt.envelope)

    def test_historical_receipt_rejects_noncanonical_json_with_valid_digest(self):
        receipt = self.receipt()
        encoded = json.dumps(receipt.payload, sort_keys=True).encode("utf-8")
        self.assertNotEqual(encoded, receipt.envelope.canonical_utf8)
        self.assertEqual(json.loads(encoded.decode("utf-8")), receipt.payload)
        object.__setattr__(receipt.envelope, "canonical_utf8", encoded)
        object.__setattr__(
            receipt.envelope, "sha256", hashlib.sha256(encoded).hexdigest(),
        )
        self.assertEqual(
            receipt.envelope.sha256, hashlib.sha256(encoded).hexdigest(),
        )
        with self.assertRaisesRegex(ValueError, "Non-canonical JSON encoding"):
            ExternalReceipt(receipt.version, receipt.envelope)

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

class ReceiptConsistencyTests(unittest.TestCase):
    """Synthetic offline cases; execution results are not attested here."""

    def context(self):
        return {
            "bank_sha256": hashlib.sha256(b"synthetic bank").hexdigest(),
            "consumed_budget": {
                "models": ["model-a", "model-a"],
                "tokens": 12,
                "proposals": 3,
                "time_seconds": 1.25,
            },
        }

    def receipt(self, **changes):
        fields = {
            "policy_sha256": hashlib.sha256(b"synthetic policy").hexdigest(),
            "bank_sha256": hashlib.sha256(b"synthetic bank").hexdigest(),
            "task_id": "synthetic-task",
            "judge_id": "unauthenticated-judge",
            "declared_result": {
                "success": False,
                "provenance": "self-declared, unauthenticated",
            },
            "consumed_budget": {
                "models": ["model-a", "model-a"],
                "tokens": 12,
                "proposals": 3,
                "time_seconds": 1.25,
            },
        }
        fields.update(changes)
        return BankExternalReceipt.create(**fields)

    def test_concordance_and_round_trip(self):
        receipt = self.receipt()
        restored = BankExternalReceipt.from_dict(
            json.loads(json.dumps(receipt.to_dict(), allow_nan=False)),
        )
        self.assertEqual(restored, receipt)
        self.assertIsNone(
            validate_receipt_consistency(restored, context=self.context()),
        )
        with self.assertRaisesRegex(ValueError, "Invalid receipt fields"):
            ExternalReceipt.from_dict(receipt.to_dict())

    def test_tampered_envelope_digest(self):
        receipt = self.receipt()
        object.__setattr__(receipt.envelope, "sha256", "0" * 64)
        with self.assertRaises(ValueError):
            validate_receipt_consistency(receipt, context=self.context())
        with self.assertRaises(ValueError):
            BankExternalReceipt(receipt.version, receipt.envelope)

    def test_tampered_envelope_version(self):
        receipt = self.receipt()
        object.__setattr__(receipt.envelope, "version", 2)
        with self.assertRaises(ValueError):
            validate_receipt_consistency(receipt, context=self.context())
        with self.assertRaises(ValueError):
            BankExternalReceipt(receipt.version, receipt.envelope)

    def test_tampered_envelope_noncanonical_json(self):
        receipt = self.receipt()
        encoded = json.dumps(receipt.payload, sort_keys=True).encode("utf-8")
        object.__setattr__(receipt.envelope, "canonical_utf8", encoded)
        object.__setattr__(
            receipt.envelope, "sha256", hashlib.sha256(encoded).hexdigest(),
        )
        with self.assertRaises(ValueError):
            validate_receipt_consistency(receipt, context=self.context())
        with self.assertRaises(ValueError):
            BankExternalReceipt(receipt.version, receipt.envelope)

    def test_absent_and_malformed_context(self):
        receipt = self.receipt()
        with self.assertRaises(ValueError):
            validate_receipt_consistency(receipt)
        for context in (None, True, 0, "", [], {}, {"extra": None}):
            with self.subTest(context=context):
                with self.assertRaises(ValueError):
                    validate_receipt_consistency(receipt, context=context)
        for field in self.context():
            context = self.context()
            del context[field]
            with self.subTest(missing=field), self.assertRaises(ValueError):
                validate_receipt_consistency(receipt, context=context)
        context = self.context()
        context["extra"] = None
        with self.assertRaises(ValueError):
            validate_receipt_consistency(receipt, context=context)

    def test_invalid_bank_in_context_and_receipt(self):
        for value in (None, True, 123, "", "invalid", "a" * 63,
                      "a" * 65, "A" * 64, "g" * 64, [], {}):
            with self.subTest(value=value):
                context = self.context()
                context["bank_sha256"] = value
                with self.assertRaises(ValueError):
                    validate_receipt_consistency(self.receipt(), context=context)
                with self.assertRaises(ValueError):
                    self.receipt(bank_sha256=value)

    def test_missing_and_extra_budget_components(self):
        for field in self.context()["consumed_budget"]:
            context = self.context()
            del context["consumed_budget"][field]
            with self.subTest(missing=field), self.assertRaises(ValueError):
                validate_receipt_consistency(self.receipt(), context=context)
        context = self.context()
        context["consumed_budget"]["extra"] = 0
        with self.assertRaises(ValueError):
            validate_receipt_consistency(self.receipt(), context=context)

    def test_invalid_budget_container(self):
        for value in (None, True, 0, "", []):
            context = self.context()
            context["consumed_budget"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_receipt_consistency(self.receipt(), context=context)

    def test_invalid_budget_components(self):
        invalid = {
            "models": (
                None, True, 0, "model-a", {}, [None], [True], [1],
                [[]], [{}], ["model-a", 1],
            ),
            "tokens": (None, True, False, -1, -0.5, 1.0, "", [], {}),
            "proposals": (None, True, False, -1, -0.5, 1.0, "", [], {}),
            "time_seconds": (None, True, False, -1, -0.5, "", [], {}),
        }
        for field, values in invalid.items():
            for value in values + (float("nan"), float("inf"), -float("inf")):
                with self.subTest(field=field, value=value):
                    context = self.context()
                    context["consumed_budget"][field] = value
                    with self.assertRaises(ValueError):
                        validate_receipt_consistency(
                            self.receipt(), context=context,
                        )
                    with self.assertRaises(ValueError):
                        self.receipt(consumed_budget=context["consumed_budget"])

    def test_each_divergence(self):
        context = self.context()
        context["bank_sha256"] = hashlib.sha256(b"other bank").hexdigest()
        with self.assertRaisesRegex(ValueError, "Bank differs"):
            validate_receipt_consistency(self.receipt(), context=context)
        for field, value in (
            ("models", ["model-a"]),
            ("models", ["model-b", "model-a"]),
            ("tokens", 13),
            ("proposals", 4),
            ("time_seconds", 1.5),
        ):
            context = self.context()
            context["consumed_budget"][field] = value
            with self.subTest(field=field, value=value):
                with self.assertRaisesRegex(ValueError, "Budget differs"):
                    validate_receipt_consistency(self.receipt(), context=context)

    def test_historical_receipt_readable_but_refused(self):
        payload = self.receipt().payload
        del payload["bank_sha256"]
        historical = ExternalReceipt.create(**payload)
        restored = ExternalReceipt.from_dict(historical.to_dict())
        self.assertEqual(restored, historical)
        with self.assertRaisesRegex(ValueError, "bank-bearing receipt"):
            validate_receipt_consistency(restored, context=self.context())
        with self.assertRaisesRegex(ValueError, "Invalid bank receipt fields"):
            BankExternalReceipt.from_dict(historical.to_dict())

    def test_concordant_provenance_remains_unauthenticated(self):
        receipt = self.receipt()
        self.assertIsNone(
            validate_receipt_consistency(receipt, context=self.context()),
        )
        self.assertEqual(receipt.payload["declared_result"], {
            "success": False,
            "provenance": "self-declared, unauthenticated",
        })
        self.assertEqual(receipt.payload["judge_id"], "unauthenticated-judge")

class PolicyReceiptConsistencyTests(unittest.TestCase):
    """Synthetic offline cases; no execution or runner proof is attested."""

    def policy(self):
        return CodingPolicy.create(**CodingPolicyTests.fields(self))

    def context(self):
        return ReceiptConsistencyTests.context(self)

    def receipt(self, policy):
        return ReceiptConsistencyTests.receipt(
            self, policy_sha256=policy.sha256,
        )

    def assert_validation(self, policy, receipt, context, error=None):
        def state():
            return copy.deepcopy((
                vars(policy) if isinstance(policy, CodingPolicy) else policy,
                vars(receipt) if isinstance(receipt, ExternalReceipt) else receipt,
                context,
            ))

        before = state()
        try:
            if error is None:
                self.assertIsNone(validate_policy_receipt_consistency(
                    policy, receipt, context=context,
                ))
            else:
                with self.assertRaisesRegex(ValueError, error):
                    validate_policy_receipt_consistency(
                        policy, receipt, context=context,
                    )
        finally:
            self.assertEqual(state(), before)

    def test_serialized_acceptance_with_different_allocated_budget(self):
        fields = CodingPolicyTests.fields(self)
        fields["task_budget"] = {
            "models": ["allocated-model"],
            "tokens": 1,
            "proposals": 1,
            "time_seconds": 0,
        }
        policy = CodingPolicy.create(**fields)
        receipt = self.receipt(policy)
        policy_data, receipt_data, context = json.loads(json.dumps(
            [policy.to_dict(), receipt.to_dict(), self.context()],
            allow_nan=False,
        ))
        restored_policy = CodingPolicy.from_dict(policy_data)
        restored_receipt = BankExternalReceipt.from_dict(receipt_data)
        self.assertEqual(restored_policy, policy)
        self.assertEqual(restored_receipt, receipt)
        self.assertNotEqual(
            restored_policy.payload["task_budget"],
            restored_receipt.payload["consumed_budget"],
        )
        self.assert_validation(restored_policy, restored_receipt, context)

    def test_other_valid_policy_is_refused(self):
        policy = self.policy()
        fields = CodingPolicyTests.fields(self)
        fields["localization"] = "Autre localisation valide"
        other = CodingPolicy.create(**fields)
        self.assertNotEqual(other.sha256, policy.sha256)
        self.assert_validation(
            other, self.receipt(policy), self.context(),
            "Receipt differs from coding policy",
        )

    def test_invalid_policy_types_including_subclass(self):
        class PolicySubclass(CodingPolicy):
            pass

        policy = self.policy()
        subclass = PolicySubclass(policy.version, policy.envelope)
        for invalid in (None, True, 1, "", [], {}, policy.to_dict(), subclass):
            with self.subTest(policy_type=type(invalid)):
                self.assert_validation(
                    invalid, self.receipt(policy), self.context(),
                    "Expected a coding policy",
                )

    def test_invalid_receipt_types_including_subclass(self):
        class ReceiptSubclass(BankExternalReceipt):
            pass

        policy = self.policy()
        receipt = self.receipt(policy)
        historical_payload = receipt.payload
        del historical_payload["bank_sha256"]
        historical = ExternalReceipt.create(**historical_payload)
        subclass = ReceiptSubclass(receipt.version, receipt.envelope)
        for invalid in (None, True, 1, "", [], {}, historical, subclass):
            with self.subTest(receipt_type=type(invalid)):
                self.assert_validation(
                    policy, invalid, self.context(), "bank-bearing receipt",
                )

    def test_tampered_versions_and_envelopes(self):
        for target in ("policy", "receipt"):
            for field, value in (
                ("version", 2),
                ("envelope", None),
                ("envelope.version", 2),
                ("envelope.sha256", "0" * 64),
                ("envelope.canonical_utf8", b"{}"),
            ):
                with self.subTest(target=target, field=field):
                    policy = self.policy()
                    receipt = self.receipt(policy)
                    obj = policy if target == "policy" else receipt
                    if field.startswith("envelope."):
                        obj = obj.envelope
                        attribute = field.split(".")[1]
                    else:
                        attribute = field
                    object.__setattr__(obj, attribute, value)
                    self.assert_validation(policy, receipt, self.context(), ".")

    def test_bank_and_each_consumed_budget_divergence(self):
        policy = self.policy()
        receipt = self.receipt(policy)
        context = self.context()
        context["bank_sha256"] = hashlib.sha256(b"other bank").hexdigest()
        self.assert_validation(policy, receipt, context, "Bank differs")
        for field, value in (
            ("models", ["model-b", "model-a"]),
            ("models", ["model-a"]),
            ("tokens", 13),
            ("proposals", 4),
            ("time_seconds", 1.5),
        ):
            with self.subTest(field=field, value=value):
                context = self.context()
                context["consumed_budget"][field] = value
                self.assert_validation(policy, receipt, context, "Budget differs")

    def test_missing_context_is_refused_without_mutation(self):
        policy = self.policy()
        self.assert_validation(
            policy, self.receipt(policy), None,
            "Expected complete external context",
        )
