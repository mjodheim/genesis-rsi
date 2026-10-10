from genesis import external_localization as external


def test_a_repository_has_one_spelling():
    spellings = ("https://github.com/Apache/Shiro.git", "https://www.github.com/apache/shiro", "http://github.com/apache/shiro/")
    assert {external.repository_key(item) for item in spellings} == {"github.com/apache/shiro"}


def test_modules_of_one_repository_fall_in_the_same_part():
    assert external.part_of("https://github.com/apache/shiro.git") == external.part_of("https://www.github.com/apache/shiro")
    parts = {external.part_of(f"https://example.org/owner/project{index}") for index in range(60)}
    assert parts == set(external.PARTS)


def test_the_bugs_kept_do_not_depend_on_the_order_they_are_listed_in():
    bugs = [str(index) for index in range(1, 40)]
    kept = external.kept_bugs("Project", bugs)
    assert len(kept) == external.PER_PROJECT and kept == external.kept_bugs("Project", reversed(bugs))
    assert external.kept_bugs("Project", ["3", "1"], 5) == external.kept_bugs("Project", ["1", "3"], 5)


def test_anything_shared_with_the_development_catalogue_is_left_out():
    used = {"used_projects": ["Lang"], "used_repositories": ["https://github.com/apache/commons-lang.git"],
            "used_revisions": ["abc"]}
    assert external.independent("Lang", "https://example.org/x", [], **used)
    assert external.independent("Lang3", "https://www.github.com/apache/commons-lang", [], **used)
    assert external.independent("Other", "https://example.org/x", ["abc", "def"], **used)
    assert external.independent("Math_4j", "https://example.org/copy", [], **used)
    assert external.independent("Other", "https://example.org/x", ["def"], **used) is None


def test_the_source_directory_is_the_one_the_patch_edits():
    paths = ["core/src/main/java/org/a/B.java"]
    assert external.source_directory(paths, "core", "src/main/java") == "core/src/main/java"
    assert external.source_directory(["src/main/java/org/a/B.java"], ".", "src/main/java") == "src/main/java"
    assert external.source_directory(["src/main/java/org/a/B.java"], "core", "src/main/java") == "src/main/java"
    assert external.source_directory(["docs/readme.txt"], ".", "src/main/java") is None


def test_the_layout_is_read_for_the_first_known_revision():
    rows = [["r1", "src", "test"], ["r2", "src/main/java", "src/test/java"], ["short"]]
    assert external.layout_of(rows, ["r9", "r2"]) == ("src/main/java", "src/test/java")
    assert external.layout_of(rows, ["r9"]) is None
