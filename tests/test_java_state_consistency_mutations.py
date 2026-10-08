"""Generalization checks using invented Java names, never benchmark patches."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from genesis import java_state_consistency_mutations, repair_strategist
from genesis.failure_localization import prioritize

JDK = Path("/home/anthony/tools/jdk11/bin")


def synthetic(thing: str = "Voucher", field: str = "label") -> str:
    getter = "get" + field.capitalize()
    return f"""
class Parent{thing} {{
  private String {field};
  Parent{thing}(String {field}) {{ this.{field} = {field}; }}
  public String {getter}() {{ return {field}; }}
}}
public class {thing} extends Parent{thing} {{
  private String {field} = null;
  public {thing}(String {field}) {{ super({field}); }}
  public String {getter}() {{
    return {field} == null ? super.{getter}() : {field};
  }}
  public boolean equals(Object obj) {{
    if (!(obj instanceof {thing})) return false;
    {thing} other = ({thing}) obj;
    if ({field} == null) {{
      if (other.{field} != null) return false;
    }} else if (!{field}.equals(other.{field})) {{
      return false;
    }}
    return true;
  }}
}}
"""


class StateConsistencyTests(unittest.TestCase):
    def test_mines_same_structure_under_unrelated_names(self):
        for name, field in (("Voucher", "label"), ("Parcel", "token")):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                path = root / (name + ".java")
                path.write_text(synthetic(name, field))
                result = java_state_consistency_mutations.generate(
                    root, include_prefixes=[name + ".java"],
                )
                self.assertEqual(result["candidate_count"], 1)
                patched = result["candidates"][0]["content_utf8"]
                self.assertIn(f"this.{field} = {field};", patched)
                self.assertEqual(
                    result["candidates"][0]["operator"],
                    "initialize_shadowed_inherited_state",
                )
                self.assertEqual(path.read_text(), synthetic(name, field))

    def test_rejects_existing_assignment_and_nonshadow_behavior(self):
        base = synthetic("Ledger", "code")
        variants = [
            base.replace("super(code); }", "super(code); this.code = code; }"),
            base.replace("code == null ? super.getCode() : code;", "return code;"),
            base.replace("private String code = null;", "private String code = \"\";"),
            base.replace("if (other.code != null)", "if (other.getCode() != null)")
                .replace("code.equals(other.code)", "getCode().equals(other.getCode())")
                .replace("if (code == null)", "if (getCode() == null)"),
        ]
        for i, src in enumerate(variants):
            with self.subTest(case=i), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "Ledger.java").write_text(src)
                self.assertEqual(
                    java_state_consistency_mutations.generate(root)["candidate_count"],
                    0,
                )

    def test_search_ranks_generic_atomic_patch_before_compositions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = []
            for name in ("Voucher", "Parcel"):
                path = root / (name + ".java")
                path.write_text(synthetic(name, "label"))
                files.append(path.name)
            hint = prioritize(
                "--- example.com.ParcelTest::testDifferentLabels\n",
                files,
            )
            self.assertEqual(hint["matched_source_paths"], ["Parcel.java"])
            search = repair_strategist.generate(
                root, include_prefixes=files,
                focus_paths=files,
                max_candidates=80, per_family_budget=80,
                source_balance_experimental=True,
                atomic_first_experimental=True,
                priority_focus_paths=hint["matched_source_paths"],
            )
            self.assertTrue(search["candidates"])
            self.assertEqual(search["candidates"][0]["path"], "Parcel.java")
            self.assertEqual(
                search["candidates"][0]["plan"]["component_operators"],
                ["initialize_shadowed_inherited_state"],
            )
            self.assertEqual(search["candidates"][0]["plan"]["depth"], 1)

    @unittest.skipUnless((JDK / "javac").is_file(), "Java compiler unavailable")
    def test_independent_behavior_of_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "Voucher.java"
            src.write_text(synthetic("Voucher", "label"))
            repair = java_state_consistency_mutations.generate(root)
            self.assertEqual(repair["candidate_count"], 1)
            src.write_text(repair["candidates"][0]["content_utf8"])
            check = root / "Check.java"
            check.write_text("""
public class Check {
  public static void main(String[] args) {
    Voucher a = new Voucher("alpha");
    Voucher b = new Voucher("beta");
    Voucher c = new Voucher("alpha");
    if (a.equals(b)) throw new AssertionError("different labels unexpectedly equal");
    if (!a.equals(c)) throw new AssertionError("same labels unexpectedly unequal");
    if (!"alpha".equals(a.getLabel())) throw new AssertionError("getter changed");
  }
}
""")
            compilation = subprocess.run(
                [str(JDK / "javac"), "-proc:none", "-d", str(root),
                 str(src), str(check)], capture_output=True, text=True,
            )
            self.assertEqual(compilation.returncode, 0, compilation.stderr)
            validation = subprocess.run(
                [str(JDK / "java"), "-cp", str(root), "Check"],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(validation.returncode, 0, validation.stderr)


if __name__ == "__main__":
    unittest.main()
