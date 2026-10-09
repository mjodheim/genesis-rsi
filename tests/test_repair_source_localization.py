import pytest
from genesis.repair_source_localization import enrich
from genesis.repair_self_improvement import sealed


def fixture(root,value='expected'):
    (root/'src').mkdir();(root/'test').mkdir()
    (root/'src/Parser.java').write_text('class Parser { static int parse(String s) { return s.length(); } }')
    (root/'test/OddTest.java').write_text('class OddTest { void fails() { int actual=Parser.parse("input"); assertEquals("'+value+'",actual); } }')
    return sealed(dict(source_directory='src',test_directory='test',failing_tests=['OddTest::fails'],
        suspect_locations=[],suspects_from_stack_trace=False,production_source=[]),'evidence_digest')


def test_assertion_localization_uses_call_not_expected_literal(tmp_path):
    evidence=fixture(tmp_path);result=enrich(tmp_path,evidence)
    assert result['suspect_locations']==[['src/Parser.java',1]]
    assert result['static_localization']['runtime_coverage'] is False
    (tmp_path/'test/OddTest.java').write_text('class OddTest { void fails() { int actual=Parser.parse("different input"); assertEquals("unrelated answer",actual); } }')
    repeated=enrich(tmp_path,evidence)
    assert repeated['suspect_locations']==result['suspect_locations']
    assert all(not row['path'].startswith('test/') for row in repeated['production_source'])


def test_existing_stack_localization_is_preserved(tmp_path):
    evidence=fixture(tmp_path);evidence.update(suspects_from_stack_trace=True,suspect_locations=[['src/Parser.java',1]])
    assert enrich(tmp_path,evidence) is evidence


def test_comments_literals_and_ambiguous_class_do_not_create_targets(tmp_path):
    evidence=fixture(tmp_path)
    (tmp_path/'test/OddTest.java').write_text('class OddTest { void fails() { String s="Parser.parse()"; /* Parser.parse(); */ assertTrue(false); } }')
    assert enrich(tmp_path,evidence)==evidence
    (tmp_path/'test/OddTest.java').write_text('class OddTest { void fails() { Parser.parse("x"); } }')
    (tmp_path/'src/other').mkdir();(tmp_path/'src/other/Parser.java').write_text('class Parser { static int parse(String s) { return 0; } }')
    assert enrich(tmp_path,evidence)==evidence


def test_symlink_targets_and_invalid_budgets_are_refused(tmp_path):
    evidence=fixture(tmp_path)
    (tmp_path/'src/Parser.java').unlink();(tmp_path/'src/Parser.java').symlink_to(tmp_path/'test/OddTest.java')
    assert enrich(tmp_path,evidence)==evidence
    with pytest.raises(ValueError):enrich(tmp_path,evidence,max_files=100)
