"""Typed hypotheses proposed from source before any independent test outcome."""
from __future__ import annotations
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
import unittest
from genesis.java_sibling_guard_mutations import generate as old_guard
from genesis.trust_root import digest_of
from genesis.v2.semantic_dsl import SemanticHypothesisError, compile_hypothesis, propose
from genesis.g12_operator_lab import _validated_outcome

JDK = Path("/home/anthony/tools/jdk11/bin")


def fixture(classname="Signal", flag="corrupt", connector="||"):
    return f"""public class {classname} {{
    private double quantity;
    private boolean {flag};
    public static final {classname} BAD = new {classname}(Double.NaN, true);
    public {classname}(double q, boolean flag) {{
        this.quantity = q;
        this.{flag} = flag;
    }}
    public {classname} join({classname} peer) {{
        Tools.checkNotNull(peer);
        return new {classname}(quantity + peer.quantity, false);
    }}
    public {classname} minus({classname} peer) {{
        Tools.checkNotNull(peer);
        if ({flag} {connector} peer.{flag}) {{
            return BAD;
        }}
        return new {classname}(quantity - peer.quantity, false);
    }}
    public {classname} times({classname} peer) {{
        Tools.checkNotNull(peer);
        if ({flag} {connector} peer.{flag}) {{
            return BAD;
        }}
        return new {classname}(quantity * peer.quantity, false);
    }}
    public boolean isBad() {{
        return {flag};
    }}
    public double value() {{
        return quantity;
    }}
}}
class Tools {{
    static void checkNotNull(Object v) {{
        if (v == null) throw new IllegalArgumentException("null input");
    }}
}}
"""


def oracle_source(class_name, connector):
    if connector == "||":
        check = f"""if (bad.join(good) != {class_name}.BAD) throw new AssertionError("must propagate bad");
                  if (good.join(bad) != {class_name}.BAD) throw new AssertionError("must propagate bad");"""
    else:
        check = f"""if (bad.join(bad) != {class_name}.BAD) throw new AssertionError("double bad should reject");
                  if (bad.join(good) == {class_name}.BAD) throw new AssertionError("single bad allowed");"""
    return f"""
public class Check {{
    public static void main(String[] args) {{
        {class_name} bad = {class_name}.BAD;
        {class_name} good = new {class_name}(3.0, false);
        {check}
        if (good.join(new {class_name}(4.0, false)).value() != 7.0)
            throw new AssertionError("normal sum changed");
        try {{ good.join(null); throw new AssertionError("null not rejected"); }}
        catch (IllegalArgumentException expected) {{ }}
    }}
}}
"""


def oracle(source, class_name, connector):
    with TemporaryDirectory() as td:
        root = Path(td)
        java = root / f"{class_name}.java"
        test = root / "Check.java"
        java.write_text(source)
        test.write_text(oracle_source(class_name, connector))
        compiler = str(JDK/"javac") if (JDK/"javac").is_file() else "javac"
        runtime = str(JDK/"java") if (JDK/"java").is_file() else "java"
        c = subprocess.run(
            [compiler, "-proc:none", "-d", str(root), str(java), str(test)],
            capture_output=True, text=True, timeout=20,
        )
        if c.returncode:
            return {"compiled":False,"full_suite_ran":False,"full_suite_pass":False,
                    "full_suite_failures":None,"test_exit":None,"error":c.stderr}
        r = subprocess.run(
            [runtime,"-cp",str(root),"Check"],capture_output=True,text=True,timeout=15
        )
        return {
            "compiled":True,"full_suite_ran":True,"full_suite_pass":r.returncode==0,
            "full_suite_failures":0 if r.returncode==0 else 1,
            "test_exit":r.returncode, "error":r.stderr[-400:],
        }


class SemanticHypothesisDSLTests(unittest.TestCase):
    def test_new_contract_names_beyond_old_guard_family(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            before=fixture("Signal","corrupt")
            source=root/"Signal.java"
            source.write_text(before)
            old=old_guard(root)
            self.assertEqual(old["candidate_count"],0)
            props=propose(root,"Signal.java")
            self.assertEqual(props["hypothesis_count"],1)
            hypothesis=props["proposals"][0]
            self.assertEqual(hypothesis["target_method"],"join")
            self.assertEqual(hypothesis["donor_methods"],["minus","times"])
            self.assertEqual(hypothesis["predicate"]["connector"],"||")
            self.assertEqual(hypothesis["placement"],"after_existing_null_check")
            patch=compile_hypothesis(root,hypothesis)
            self.assertEqual(patch["source_sha256"],sha256(before.encode()).hexdigest())
            self.assertIn("if (corrupt || peer.corrupt)",patch["content_utf8"])
            self.assertEqual(source.read_text(),before)
            self.assertTrue(props["no_evaluator_feedback_seen"])
            self.assertFalse(patch["candidate_validated"])
            self.assertFalse(patch["compiler_ran"])

    @unittest.skipUnless((JDK/"javac").exists(), "Java compiler missing")
    def test_pretest_hypothesis_meets_separate_behavior_oracle(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            before=fixture("Signal","corrupt")
            (root/"Signal.java").write_text(before)
            record=propose(root,"Signal.java")
            patch=compile_hypothesis(root,record["proposals"][0])
            frozen={
                "hypothesis_digest":record["proposals"][0]["hypothesis_digest"],
                "candidate_sha256":patch["candidate_sha256"],
                "before_sha256":patch["source_sha256"],
            }
            locked=digest_of(frozen)
            baseline=oracle(before,"Signal","||")
            repaired=oracle(patch["content_utf8"],"Signal","||")
            self.assertTrue(baseline["compiled"])
            self.assertFalse(baseline["full_suite_pass"])
            self.assertTrue(_validated_outcome(repaired))
            self.assertEqual(digest_of(frozen),locked)
            self.assertEqual((root/"Signal.java").read_text(),before)

    @unittest.skipUnless((JDK/"javac").exists(), "Java compiler missing")
    def test_and_connector_and_renamed_fields(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            before=fixture("Parcel","flagged","&&")
            (root/"Parcel.java").write_text(before)
            self.assertEqual(old_guard(root)["candidate_count"],0)
            record=propose(root,"Parcel.java")
            self.assertEqual(record["hypothesis_count"],1)
            patch=compile_hypothesis(root,record["proposals"][0])
            self.assertIn("if (flagged && peer.flagged)",patch["content_utf8"])
            self.assertFalse(oracle(before,"Parcel","&&")["full_suite_pass"])
            self.assertTrue(_validated_outcome(oracle(patch["content_utf8"],"Parcel","&&")))

    def test_stale_file_and_rehashed_unsupported_hypothesis_refused(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            source=root/"Signal.java"
            source.write_text(fixture())
            rec=propose(root,"Signal.java")["proposals"][0]
            modified=deepcopy(rec)
            modified["return_constant"]="OTHER"
            modified["hypothesis_digest"]=digest_of({
                k:v for k,v in modified.items() if k!="hypothesis_digest"
            })
            with self.assertRaisesRegex(SemanticHypothesisError,"grounded"):
                compile_hypothesis(root,modified)
            source.write_text(fixture().replace("private double quantity;", "private double adjusted;"))
            with self.assertRaisesRegex(SemanticHypothesisError,"source changed"):
                compile_hypothesis(root,rec)

    def test_requires_static_final_typed_result_and_boolean_members(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            java=root/"Signal.java"
            original=fixture()
            java.write_text(original.replace(
                "public static final Signal BAD", "public final Signal BAD"
            ))
            self.assertEqual(propose(root,"Signal.java")["hypothesis_count"],0)
            java.write_text(original.replace("private boolean corrupt;", "private Object corrupt;"))
            self.assertEqual(propose(root,"Signal.java")["hypothesis_count"],0)

    def test_donor_methods_cannot_be_borrowed_across_java_classes(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            primary=fixture()
            # Another unrelated Java type has a similar method but no
            # supporting donor methods; this must NOT borrow Signal's facts.
            secondary="""class Parcel {
                boolean corrupt;
                static final Parcel BAD = new Parcel();
                public Parcel join(Parcel peer) {
                    return new Parcel();
                }
            }"""
            (root/"Signal.java").write_text(primary+"\n"+secondary)
            found=propose(root,"Signal.java")
            self.assertEqual(found["hypothesis_count"],1)
            self.assertEqual(found["proposals"][0]["target_return_type"],"Signal")

    def test_no_peer_quorum_and_negative_cases(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            source=fixture("Signal")
            source=source.replace(
                """if (corrupt || peer.corrupt) {
            return BAD;
        }""", "",1
            )
            (root/"Signal.java").write_text(source)
            self.assertEqual(propose(root,"Signal.java")["hypothesis_count"],0)
        with TemporaryDirectory() as td:
            root=Path(td)
            (root/"Signal.java").write_text(fixture())
            for badpath in ("../Signal.java", "/tmp/Signal.java", "tests/Signal.java"):
                with self.subTest(badpath=badpath), self.assertRaises((SemanticHypothesisError,FileNotFoundError)):
                    propose(root,badpath)
            with self.assertRaises(SemanticHypothesisError):
                propose(root,"Signal.java",max_hypotheses=100)


if __name__=="__main__":
    unittest.main()
