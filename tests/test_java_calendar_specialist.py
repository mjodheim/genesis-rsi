from pathlib import Path

from genesis import java_calendar_specialist as jcs


def _fixture() -> str:
    return """import java.util.Calendar;
import java.util.Date;
class CalendarOps {
    private static int[][] fields = new int[][] {{ Calendar.MILLISECOND }, { Calendar.SECOND }, { Calendar.MINUTE }};
    private static void adjust(Calendar calendar, int target, boolean shouldRound) {
        if (calendar.get(Calendar.YEAR) > 1000000) {
            throw new ArithmeticException();
        }

        // truncate milliseconds
        // truncate seconds
        // truncate minutes
        // reset time

        boolean raise = false;
        for (int i = 0; i < fields.length; i++) {
            int delta = 0;
            boolean deltaSet = false;
            if (!deltaSet) {
                int min = calendar.getActualMinimum(fields[i][0]);
                int max = calendar.getActualMaximum(fields[i][0]);
                delta = calendar.get(fields[i][0]) - min;
                raise = delta > ((max - min) / 2);
            }
            calendar.set(fields[i][0], calendar.get(fields[i][0]) - delta);
        }
    }
}
"""


def test_generates_coordinated_calendar_normalization(tmp_path: Path) -> None:
    p = tmp_path / "src" / "CalendarOps.java"
    p.parent.mkdir()
    p.write_text(_fixture(), encoding="utf-8")
    result = jcs.generate(tmp_path, include_prefixes=["src"], max_candidates=10)
    assert result["candidate_count"] == 1
    text = result["candidates"][0]["content_utf8"]
    assert "Calendar.MILLISECOND" in text
    assert "* 60000L" in text
    assert "if (delta != 0)" in text
    assert "calendar.setTime(" in text


def test_uses_captured_variable_names_not_fixed_names(tmp_path: Path) -> None:
    p = tmp_path / "src" / "CalendarOps.java"
    p.parent.mkdir()
    p.write_text(_fixture(), encoding="utf-8")
    candidate = jcs.generate(tmp_path, include_prefixes=["src"], max_candidates=10)["candidates"][0]
    detail = candidate["detail"]
    assert detail["calendar_var"] == "calendar"
    assert detail["field_var"] == "target"
    assert detail["round_var"] == "shouldRound"
    assert detail["offset_var"] == "delta"


def test_requires_calendar_truncation_structure(tmp_path: Path) -> None:
    p = tmp_path / "src" / "Other.java"
    p.parent.mkdir()
    p.write_text(
        """import java.util.Calendar;
class Other {
    private static void f(Calendar c, int x, boolean y) {
        c.set(x, 1);
    }
}
""",
        encoding="utf-8",
    )
    result = jcs.generate(tmp_path, include_prefixes=["src"], max_candidates=10)
    assert result["candidate_count"] == 0
