from __future__ import annotations

import re
from dataclasses import dataclass, field


HUNK_RE = re.compile(
    r"^@@ -(?P<old>\d+)(?:,(?P<old_count>\d+))? "
    r"\+(?P<new>\d+)(?:,(?P<new_count>\d+))? @@"
)


class DiffParseError(ValueError):
    pass


@dataclass(frozen=True)
class ChangedLine:
    kind: str
    text: str
    old_line: int | None
    new_line: int | None


@dataclass
class DiffFile:
    old_path: str
    new_path: str
    changed_lines: list[ChangedLine] = field(default_factory=list)


@dataclass
class ParsedDiff:
    files: list[DiffFile]
    raw: str

    @property
    def changed_new_lines(self) -> dict[str, set[int]]:
        result: dict[str, set[int]] = {}
        for diff_file in self.files:
            lines = {
                line.new_line
                for line in diff_file.changed_lines
                if line.kind == "add" and line.new_line is not None
            }
            result[diff_file.new_path] = lines
        return result

    def compact_context(self) -> str:
        blocks: list[str] = []
        for diff_file in self.files:
            lines = [f"FILE: {diff_file.new_path}"]
            for changed in diff_file.changed_lines:
                marker = "+" if changed.kind == "add" else "-"
                number = changed.new_line if changed.kind == "add" else changed.old_line
                lines.append(f"{marker}{number}: {changed.text}")
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)


def _clean_path(value: str) -> str:
    value = value.strip().split("\t", 1)[0]
    if value.startswith("a/") or value.startswith("b/"):
        return value[2:]
    return value


def parse_unified_diff(raw: str) -> ParsedDiff:
    if not raw.strip():
        raise DiffParseError("diff is empty")

    files: list[DiffFile] = []
    current: DiffFile | None = None
    old_line: int | None = None
    new_line: int | None = None
    pending_old_path: str | None = None
    expected_old_count: int | None = None
    expected_new_count: int | None = None
    consumed_old = 0
    consumed_new = 0

    def validate_hunk() -> None:
        if expected_old_count is None or expected_new_count is None:
            return
        if consumed_old != expected_old_count or consumed_new != expected_new_count:
            raise DiffParseError(
                "hunk line counts do not match header: "
                f"expected -{expected_old_count}/+{expected_new_count}, "
                f"observed -{consumed_old}/+{consumed_new}"
            )

    for line in raw.splitlines():
        if line.startswith("--- "):
            validate_hunk()
            expected_old_count = expected_new_count = None
            pending_old_path = _clean_path(line[4:])
            continue
        if line.startswith("+++ "):
            old_path = pending_old_path or "/dev/null"
            current = DiffFile(old_path=old_path, new_path=_clean_path(line[4:]))
            files.append(current)
            old_line = new_line = None
            continue

        hunk = HUNK_RE.match(line)
        if hunk and current is not None:
            validate_hunk()
            old_line = int(hunk.group("old"))
            new_line = int(hunk.group("new"))
            expected_old_count = int(hunk.group("old_count") or "1")
            expected_new_count = int(hunk.group("new_count") or "1")
            consumed_old = consumed_new = 0
            continue

        if current is None or old_line is None or new_line is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            current.changed_lines.append(ChangedLine("add", line[1:], None, new_line))
            new_line += 1
            consumed_new += 1
        elif line.startswith("-") and not line.startswith("---"):
            current.changed_lines.append(ChangedLine("delete", line[1:], old_line, None))
            old_line += 1
            consumed_old += 1
        elif line.startswith(" "):
            old_line += 1
            new_line += 1
            consumed_old += 1
            consumed_new += 1
        elif line.startswith("\\ No newline at end of file"):
            continue

    validate_hunk()
    files = [item for item in files if item.changed_lines]
    if not files:
        raise DiffParseError("no changed lines found in unified diff")
    return ParsedDiff(files=files, raw=raw)
