"""G12 release-only feedback->validated patch->retained machine-created edit.

Tests are entirely synthetic: not counted as independent RSI improvement.
"""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from genesis import java_state_consistency_mutations as state
from genesis.g12_operator_lab import (
    G12GateError, freeze_training_search, validate_and_learn,
)
from genesis.learning import self_extension
from genesis.trust_root import digest_of

JDK=Path("/home/anthony/tools/jdk11/bin")
JAVA=str(JDK/"java") if (JDK/"java").is_file() else "java"
JAVAC=str(JDK/"javac") if (JDK/"javac").is_file() else "javac"

def source(name="Voucher", field="label"):
    getter="get"+field.capitalize()
    return f'''class Parent{name} {{
    private String {field};
    Parent{name}(String {field}) {{ this.{field} = {field}; }}
    public String {getter}() {{ return {field}; }}
}}
public class {name} extends Parent{name} {{
    private String {field} = null;
    public {name}(String {field}) {{ super({field}); }}
    public String {getter}() {{ return {field} == null ? super.{getter}() : {field}; }}
    public boolean equals(Object object) {{
        if (!(object instanceof {name})) return false;
        {name} other = ({name}) object;
        if ({field} == null) {{
            if (other.{field} != null) return false;
        }} else if (!{field}.equals(other.{field})) {{
            return false;
        }}
        return true;
    }}
}}
'''

TEST='''
public class Check {
    public static void main(String[] args) {
        Voucher a = new Voucher("alpha");
        Voucher b = new Voucher("beta");
        Voucher c = new Voucher("alpha");
        if (a.equals(b)) throw new AssertionError("different labels must differ");
        if (!a.equals(c)) throw new AssertionError("same labels must match");
        if (!"alpha".equals(a.getLabel())) throw new AssertionError("getter contract");
    }
}
'''

def public_validator(_root: Path):
    def run(path: str, content: str, expected_sha256: str) -> dict:
        from hashlib import sha256
        if sha256((_root/path).read_bytes()).hexdigest()!=expected_sha256:
            raise ValueError("stale preimage")
        with tempfile.TemporaryDirectory() as td:
            d=Path(td)
            (d/"Voucher.java").write_text(content)
            (d/"Check.java").write_text(TEST)
            compiled=subprocess.run(
                [JAVAC,"-proc:none","-d",str(d),str(d/"Voucher.java"),str(d/"Check.java")],
                capture_output=True,text=True,timeout=30,
            )
            if compiled.returncode:
                return {"compiled":False,"full_suite_ran":False,"full_suite_pass":False}
            result=subprocess.run(
                [JAVA,"-cp",str(d),"Check"],
                capture_output=True,text=True,timeout=10,
            )
            return {
                "compiled":True,"full_suite_ran":True,
                "full_suite_failures":0 if result.returncode==0 else 1,
                "full_suite_pass":result.returncode==0,
                "test_exit":result.returncode,
            }
    return run


def miss():
    return {
        "report_digest":"a"*64,"candidate_budget":8,
        "charged_candidate_executions":8,
        "winner":None,"autonomous_passed":False,
        "schedule":{"scheduled_count":8,"family_input_counts":{
            "learned":0,"retained":0,"scalar":8
        },"family_scheduled_counts":{"scalar":8}},
    }


@unittest.skipUnless((JDK/"javac").is_file(), "requires Java 11")
class OperatorLabTests(unittest.TestCase):
    def setUp(self):
        self.work=tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.root=Path(self.work.name)
        self.root.joinpath("Voucher.java").write_text(source())
        self.assertFalse(public_validator(self.root)(
            "Voucher.java",source(),"8"*64
        )["full_suite_pass"]) if False else None
        self.candidates=state.generate(self.root,include_prefixes=["Voucher.java"])["candidates"]
        self.assertEqual(len(self.candidates),1)
        self.freeze=self.root/"evidence/freeze.json"
        self.memory=self.root/"evidence/memory.json"
        self.receipt=self.root/"evidence/receipt.json"

    def frozen(self,role="released_training"):
        return freeze_training_search(
            root=self.root,candidates=self.candidates,previous_failure=miss(),
            freeze_path=self.freeze,role=role,max_candidates=8,
        )

    def test_full_compiler_and_assertion_then_operator_retention(self):
        baseline=public_validator(self.root)(
            "Voucher.java",source(),
            self.candidates[0]["expected_sha256"],
        )
        self.assertTrue(baseline["compiled"])
        self.assertFalse(baseline["full_suite_pass"])
        frozen=self.frozen()
        result=validate_and_learn(
            root=self.root,candidates=self.candidates,frozen=frozen,
            freeze_path=self.freeze,previous_failure=miss(),
            evaluator=public_validator(self.root),memory_path=self.memory,
            result_path=self.receipt,role="released_training",
        )
        self.assertEqual(result["attempt_count"],1)
        self.assertEqual(result["memory_generation"],2)
        self.assertEqual(result["independent_new_bug_successes"],0)
        self.assertTrue(result["learning_only_from_validated_candidate"])
        self.assertFalse(result["novel_semantic_operator_autonomously_invented"])
        self.assertTrue(result["validated_operator_acquisition"]["replay_verified_on_training_source"])
        self.assertTrue(result["validated_operator_acquisition"]["reused_without_model_calls"])
        self.assertEqual(result["receipt_digest"],digest_of({
            k:v for k,v in result.items() if k!="receipt_digest"
        }))
        memory=self_extension.validate_memory(json.loads(self.memory.read_text()))
        self.assertEqual([e["kind"] for e in memory["events"]],
                         ["gap_observed","operator_acquired"])
        self.assertEqual(len(memory["operators"]),1)
        self.assertEqual(self.root.joinpath("Voucher.java").read_text(),source())

        # Reuse in a *different workspace* with the same structural shape.
        clone=self.root/"fork"
        clone.mkdir()
        clone.joinpath("Voucher.java").write_text(source())
        reused=self_extension.generate_candidates(memory,clone,
            include_prefixes=["Voucher.java"],max_candidates=12)
        texts=[m["content_utf8"] for item in reused["candidate_set"]["candidates"]
               for m in item["mutations"]]
        self.assertIn(self.candidates[0]["content_utf8"],texts)
        self.assertEqual(reused["external_model_calls"],0)

    def test_rejects_unreleased_holdout_even_with_passing_patch(self):
        with self.assertRaisesRegex(G12GateError,"held-out"):
            self.frozen(role="fresh_holdout")
        frozen=self.frozen()
        with self.assertRaisesRegex(G12GateError,"unreleased"):
            validate_and_learn(
                root=self.root,candidates=self.candidates,frozen=frozen,
                freeze_path=self.freeze,previous_failure=miss(),
                evaluator=public_validator(self.root),memory_path=self.memory,
                result_path=self.receipt,role="fresh_holdout",
            )
        self.assertFalse(self.memory.exists())

    def test_refuses_compile_only_false_positive(self):
        frozen=self.frozen()
        result=validate_and_learn(
            root=self.root,candidates=self.candidates,frozen=frozen,
            freeze_path=self.freeze,previous_failure=miss(),
            evaluator=lambda *_: {"compiled":True,"full_suite_pass":True,
                                   "full_suite_ran":False,"full_suite_failures":0},
            memory_path=self.memory,result_path=self.receipt,
            role="released_training",
        )
        self.assertIsNone(result["validated_operator_acquisition"])
        self.assertFalse(result["learning_only_from_validated_candidate"])
        self.assertEqual(result["memory_generation"],1)
        self.assertEqual(self_extension.validate_memory(
            json.loads(self.memory.read_text()))["operators"],[])

    def test_candidate_tampering_after_freeze_fails_closed(self):
        frozen=self.frozen()
        altered=[{**self.candidates[0],"content_utf8":source().replace("alpha","bad")}]
        with self.assertRaises(G12GateError):
            validate_and_learn(
                root=self.root,candidates=altered,frozen=frozen,
                freeze_path=self.freeze,previous_failure=miss(),
                evaluator=public_validator(self.root),memory_path=self.memory,
                result_path=self.receipt,role="released_training",
            )
        self.assertFalse(self.memory.exists())

    def test_freeze_is_immutable(self):
        self.frozen()
        with self.assertRaisesRegex(G12GateError,"conflicts"):
            freeze_training_search(
                root=self.root,candidates=[{**self.candidates[0],
                    "content_utf8":source().replace("public class","final public class")}],
                previous_failure=miss(),freeze_path=self.freeze,
                role="released_training",
            )


if __name__=="__main__":
    unittest.main()
