from pathlib import Path

import pytest

from src.diff_parser import DiffParseError, parse_unified_diff


ROOT = Path(__file__).resolve().parents[1]


def test_parse_sample_diff_tracks_new_line_numbers() -> None:
    raw = (ROOT / "experiment/samples/case_02_none_access.diff").read_text(
        encoding="utf-8"
    )
    parsed = parse_unified_diff(raw)

    assert len(parsed.files) == 1
    assert parsed.files[0].new_path == "app/profile_service.py"
    assert parsed.changed_new_lines["app/profile_service.py"] == {8, 9, 10, 11, 12}
    assert "+11:     user = User.query.filter_by(id=user_id).first()" in parsed.compact_context()


def test_empty_diff_is_rejected() -> None:
    with pytest.raises(DiffParseError, match="empty"):
        parse_unified_diff("")


def test_incorrect_hunk_counts_are_rejected() -> None:
    raw = "--- a/demo.py\n+++ b/demo.py\n@@ -1,2 +1,3 @@\n old\n+new\n"
    with pytest.raises(DiffParseError, match="hunk line counts"):
        parse_unified_diff(raw)
