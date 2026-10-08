"""Generic stateful streaming iterator candidate and negative controls."""
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from genesis import java_stream_iterator_mutations
from genesis import repair_strategist

JDK=Path('/home/anthony/tools/jdk11/bin')


def invented(cls='QueueRows',field='pending'):
    return f'''
import java.util.*;
public class {cls} implements Iterable<String> {{
    private final Iterator<String> producer;
    public {cls}(List<String> values) {{ producer = values.iterator(); }}
    @Override
    public Iterator<String> iterator() {{
        return new Iterator<String>() {{
            private String {field};
            private String read() {{
                return producer.hasNext() ? producer.next() : null;
            }}
            @Override
            public boolean hasNext() {{
                if (this.{field} == null) {{
                    this.{field} = this.read();
                }}
                return this.{field} != null;
            }}
            @Override
            public String next() {{
                String got = this.{field};
                this.{field} = null;
                if (got == null) {{
                    got = this.read();
                }}
                return got;
            }}
        }};
    }}
}}
'''


class StatePreservationTests(unittest.TestCase):
    def test_generates_transfer_in_unrelated_renamed_streams(self):
        for cls,field in (('QueueRows','pending'),('PacketFeed','lookahead')):
            with self.subTest(cls=cls), TemporaryDirectory() as d:
                root=Path(d); file=root/(cls+'.java'); original=invented(cls,field)
                file.write_text(original)
                out=java_stream_iterator_mutations.generate(root)
                self.assertEqual(out['candidate_count'],1)
                repaired=out['candidates'][0]['content_utf8']
                self.assertIn('this.genesisStreamingIterator',repaired)
                self.assertIn('private transient Iterator<String> genesisStreamingIterator;',repaired)
                self.assertNotIn('@Override\n    private',repaired)
                self.assertEqual(file.read_text(),original)

    def test_no_candidate_for_stateless_collection_iterator(self):
        source='''
import java.util.*;
public class NormalRows implements Iterable<String> {
  private List<String> rows = Arrays.asList("a","b");
  @Override public Iterator<String> iterator() {
    return new Iterator<String>() {
      private int index;
      @Override public boolean hasNext() { return index < rows.size(); }
      @Override public String next() { return rows.get(index++); }
    };
  }
}
'''
        with TemporaryDirectory() as d:
            path=Path(d)/'NormalRows.java';path.write_text(source)
            out=java_stream_iterator_mutations.generate(d)
            self.assertEqual(out['candidate_count'],0)

    def test_planner_only_enabled_explicitly(self):
        with TemporaryDirectory() as d:
            path=Path(d)/'QueueRows.java';path.write_text(invented())
            opts=dict(include_prefixes=['QueueRows.java'],focus_paths=['QueueRows.java'],
                      max_candidates=30,per_family_budget=30,atomic_first_experimental=True)
            old=repair_strategist.generate(d,**opts)
            new=repair_strategist.generate(d,**opts,stream_iterator_experimental=True)
            opname='java_reuse_stateful_stream_iterator'
            self.assertFalse(any(opname in r['plan']['component_operators'] for r in old['candidates']))
            self.assertEqual(new['candidates'][0]['plan']['component_operators'],[opname])
            self.assertTrue(new['g11_stream_iterator_experimental'])

    @unittest.skipUnless((JDK/'javac').exists(),'JDK unavailable')
    def test_previously_failing_lookahead_behavior_is_repaired(self):
        with TemporaryDirectory() as d:
            root=Path(d)
            src=root/'QueueRows.java';src.write_text(invented())
            checker=root/'Check.java'
            checker.write_text('''
import java.util.*;
public class Check {
 public static void main(String[] args) {
    QueueRows rows = new QueueRows(Arrays.asList("one","two","three"));
    if (!rows.iterator().next().equals("one")) throw new AssertionError("first");
    if (!rows.iterator().hasNext()) throw new AssertionError("expected another");
    if (!rows.iterator().next().equals("two"))
        throw new AssertionError("lost prefetched element");
 }
}
''')
            def run():
                compiled=subprocess.run(
                    [str(JDK/'javac'),'-proc:none','-d',str(root),str(src),str(checker)],
                    capture_output=True,text=True,timeout=15)
                self.assertEqual(compiled.returncode,0,compiled.stderr)
                return subprocess.run([str(JDK/'java'),'-cp',str(root),'Check'],
                                      capture_output=True,text=True,timeout=15)
            self.assertNotEqual(run().returncode,0)
            patch=java_stream_iterator_mutations.generate(root)['candidates'][0]
            src.write_text(patch['content_utf8'])
            ok=run()
            self.assertEqual(ok.returncode,0,ok.stderr)


if __name__=='__main__':
    unittest.main()
