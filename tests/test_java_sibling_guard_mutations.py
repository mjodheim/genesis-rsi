"""Generic repeated-sibling guard transfer across unrelated Java class names."""
import subprocess
from pathlib import Path
import tempfile
import unittest

from genesis import java_sibling_guard_mutations

JDK = Path("/home/anthony/tools/jdk11/bin")


def case(classname: str = "Signal", field: str = "isInvalid") -> str:
    return f"""
public class {classname} {{
  private final double payload;
  private final boolean {field};
  static final {classname} INVALID = new {classname}(Double.NaN);
  public {classname}(double val) {{
      payload = val;
      {field} = Double.isNaN(val);
  }}
  public {classname} plus({classname} other) {{
      Tools.checkNotNull(other);
      return new {classname}(payload + other.payload);
  }}
  public {classname} minus({classname} other) {{
      Tools.checkNotNull(other);
      if ({field} || other.{field}) {{
          return INVALID;
      }}
      return new {classname}(payload - other.payload);
  }}
  public {classname} times({classname} other) {{
      Tools.checkNotNull(other);
      if ({field} || other.{field}) {{
          return INVALID;
      }}
      return new {classname}(payload * other.payload);
  }}
  public {classname} divide({classname} other) {{
      Tools.checkNotNull(other);
      if ({field} || other.{field}) {{
          return INVALID;
      }}
      return new {classname}(payload / other.payload);
  }}
  boolean invalid() {{ return {field}; }}
  double value() {{ return payload; }}
}}
class Tools {{
    static void checkNotNull(Object value) {{
       if (value == null) throw new IllegalArgumentException();
    }}
}}
"""


class SiblingGuardTests(unittest.TestCase):
    def test_detects_missing_guard_across_renamed_code(self):
        for cls, fld in (("Signal", "isInvalid"), ("Coordinates", "isDamaged")):
            with self.subTest(cls=cls), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                file = root / (cls + ".java")
                file.write_text(case(cls, fld))
                output = java_sibling_guard_mutations.generate(root)
                self.assertEqual(output["candidate_count"], 1)
                candidate = output["candidates"][0]
                self.assertIn(f"if ({fld} || other.{fld})", candidate["content_utf8"])
                self.assertEqual(candidate["detail"]["donor_method_count"], 3)
                self.assertEqual(candidate["operator"], "java_transfer_sibling_invalid_state_guard")
                self.assertNotEqual(candidate["content_utf8"], file.read_text())
                self.assertEqual(file.read_text(), case(cls, fld))

    def test_no_duplicate_guard_if_target_already_has_it(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = case("Sample")
            source = source.replace(
                "return new Sample(payload + other.payload);",
                "if (isInvalid || other.isInvalid) { return INVALID; }\n"
                "return new Sample(payload + other.payload);",
            )
            (root / "Sample.java").write_text(source)
            self.assertEqual(
                java_sibling_guard_mutations.generate(root)["candidate_count"], 0
            )

    def test_no_donor_quorum_no_candidate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = case("RecordX")
            source = source.replace(
                "if (isInvalid || other.isInvalid) {\n          return INVALID;\n      }",
                "if (isInvalid || other.isInvalid) {\n          return INVALID;\n      }",
            )
            # Strip two occurrences by targeting all guards after the first.
            exact = "if (isInvalid || other.isInvalid) {\n          return INVALID;\n      }"
            if exact in source:
                position = source.find(exact)
                source = source[:position+len(exact)] + source[position+len(exact):].replace(
                    exact, "", 2
                )
            (root / "RecordX.java").write_text(source)
            self.assertEqual(
                java_sibling_guard_mutations.generate(root)["candidate_count"], 0
            )

    @unittest.skipUnless((JDK/"javac").exists(), "JDK unavailable")
    def test_compiler_and_independent_behavior_oracle(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            file = root / "Signal.java"
            file.write_text(case())
            variant = java_sibling_guard_mutations.generate(root)["candidates"][0]
            file.write_text(variant["content_utf8"])
            check = root / "Check.java"
            check.write_text("""
public class Check {
  public static void main(String[] args) {
    Signal ok = new Signal(3.0);
    Signal invalid = Signal.INVALID;
    if (!ok.plus(invalid).invalid()) throw new AssertionError("expected special state");
    if (ok.plus(new Signal(2.0)).value() != 5.0) throw new AssertionError("normal sum");
  }
}""")
            compiled = subprocess.run(
                [str(JDK/"javac"), "-proc:none", "-d", str(root), str(file), str(check)],
                capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            tested = subprocess.run(
                [str(JDK/"java"), "-cp", str(root), "Check"],
                capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(tested.returncode, 0, tested.stderr)


if __name__ == "__main__":
    unittest.main()
