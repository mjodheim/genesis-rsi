"""Lexical public failing-test context is useful but not proof of a fault."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from genesis.failure_localization import prioritize_from_public_test_source

class PublicTestSourceContext(unittest.TestCase):
    def create(self, temp):
        root=Path(temp)
        test=root/'src/test/java/p/functional/ScenarioTest.java'
        test.parent.mkdir(parents=True)
        return root,test

    def test_selects_class_invoked_in_public_failed_test(self):
        with TemporaryDirectory() as tmp:
            root,test=self.create(tmp)
            test.write_text('''
package p.functional;
class ScenarioTest {
  @Test public void broken() {
    Result real = Decoder.decode("A");
    assertNotNull(real);
  }
  @Test public void irrelevant() {
    Irrelevant other = new Irrelevant();
  }
}
''')
            opts=dict(project_root=root,test_source_dir='src/test/java',
                failing_tests_text='--- p.functional.ScenarioTest::broken\n',
                source_paths=['src/main/java/p/Irrelevant.java','src/main/java/p/Decoder.java',
                              'src/main/java/p/Result.java'])
            ranked=prioritize_from_public_test_source(**opts)
            self.assertEqual(ranked['selected_source_paths'][0],'src/main/java/p/Decoder.java')
            self.assertFalse(ranked['fault_location_proven'])
            self.assertFalse(ranked['human_patch_consulted'])
            self.assertTrue(ranked['ranked_evidence'][0]['score']>0)

    def test_ignores_string_and_comment_mentions(self):
        with TemporaryDirectory() as tmp:
            root,test=self.create(tmp)
            test.write_text('''
class ScenarioTest {
 @Test public void broken() {
   String s = "Irrelevant";
   // Irrelevant Irrelevant
   Result real = Decoder.decode(s);
 }
}
''')
            result=prioritize_from_public_test_source(
                project_root=root,test_source_dir='src/test/java',
                failing_tests_text='--- p.functional.ScenarioTest::broken\n',
                source_paths=['src/Irrelevant.java','src/Decoder.java','src/Result.java'])
            self.assertEqual(result['selected_source_paths'][0],'src/Decoder.java')
            irrelevant=next(r for r in result['ranked_evidence'] if r['path']=='src/Irrelevant.java')
            self.assertEqual(irrelevant['score'],0)

    def test_fallback_deterministic_no_test_file_and_bounded(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            result=prioritize_from_public_test_source(
                project_root=root,test_source_dir='src/test/java',
                failing_tests_text='--- p.MissingTest::foo\n',
                source_paths=[f'src/F{i}.java' for i in range(40)],max_focus_files=12)
            self.assertEqual(result['selected_focus_count'],12)
            self.assertEqual(result['tested_method_count'],0)
            self.assertEqual(result['positive_evidence_source_count'],0)

if __name__=='__main__':
    unittest.main()
