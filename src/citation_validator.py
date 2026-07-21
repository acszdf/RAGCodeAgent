from __future__ import annotations

import re

from .diff_parser import ParsedDiff
from .schemas import (
    CitationCheck,
    KnowledgeChunk,
    LocationCheck,
    QualityCheck,
    ReviewIssue,
    ReviewPayload,
)


def _normalize(value: str) -> str:
    rendered_text = value.replace("`", "")
    return re.sub(r"\s+", " ", rendered_text).strip()


def validate_citations(
    review: ReviewPayload,
    retrieved_chunks: list[KnowledgeChunk],
) -> list[CitationCheck]:
    chunks = {chunk.chunk_id: chunk for chunk in retrieved_chunks}
    checks: list[CitationCheck] = []
    for issue in review.issues:
        for citation in issue.citations:
            chunk = chunks.get(citation.chunk_id)
            if chunk is None:
                checks.append(
                    CitationCheck(
                        issue_id=issue.issue_id,
                        chunk_id=citation.chunk_id,
                        valid=False,
                        reason="chunk_id was not present in retrieved context",
                    )
                )
                continue
            if citation.source != chunk.source or citation.section != chunk.section:
                checks.append(
                    CitationCheck(
                        issue_id=issue.issue_id,
                        chunk_id=citation.chunk_id,
                        valid=False,
                        reason="source or section does not match the retrieved chunk",
                    )
                )
                continue
            if _normalize(citation.quote) not in _normalize(chunk.text):
                checks.append(
                    CitationCheck(
                        issue_id=issue.issue_id,
                        chunk_id=citation.chunk_id,
                        valid=False,
                        reason="quote is not a verbatim excerpt from the retrieved chunk",
                    )
                )
                continue
            checks.append(
                CitationCheck(
                    issue_id=issue.issue_id,
                    chunk_id=citation.chunk_id,
                    valid=True,
                    reason="source, section, chunk_id, and quote match",
                )
            )
    return checks


def validate_locations(review: ReviewPayload, parsed: ParsedDiff) -> list[LocationCheck]:
    changed_lines = parsed.changed_new_lines
    checks: list[LocationCheck] = []
    for issue in review.issues:
        if issue.file not in changed_lines:
            checks.append(
                LocationCheck(
                    issue_id=issue.issue_id,
                    valid=False,
                    reason=f"file {issue.file!r} is not present in the diff",
                )
            )
            continue
        if issue.line_start not in changed_lines[issue.file]:
            checks.append(
                LocationCheck(
                    issue_id=issue.issue_id,
                    valid=False,
                    reason="line_start is not an added line in the diff",
                )
            )
            continue
        checks.append(
            LocationCheck(
                issue_id=issue.issue_id,
                valid=True,
                reason="file and line_start point to an added line",
            )
        )
    return checks


def filter_semantically_invalid_issues(
    review: ReviewPayload,
) -> tuple[ReviewPayload, list[QualityCheck]]:
    checks: list[QualityCheck] = []
    accepted: list[ReviewIssue] = []
    contradiction_markers = (
        "already correct",
        "no issue",
        "remove this finding",
        "will remove this finding",
    )
    for issue in review.issues:
        original = f"{issue.problem}\n{issue.suggestion}\n{issue.explanation}"
        combined = original.lower()
        reason = "passed deterministic semantic checks"
        valid = True
        if any(marker in combined for marker in contradiction_markers):
            valid = False
            reason = "finding contains an explicit self-contradiction"
        elif issue.category == "style" and (
            "mixedcase" in combined or "lowercase_with_underscores" in combined
        ):
            identifiers = re.findall(r"`([A-Za-z_][A-Za-z0-9_]*)`", original)
            if not identifiers:
                identifiers = re.findall(
                    r"'([A-Za-z_][A-Za-z0-9_]*)'", original
                )
            if identifiers and all(
                re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", name)
                for name in identifiers[:1]
            ):
                valid = False
                reason = "identifier already satisfies lowercase_with_underscores"
        checks.append(QualityCheck(issue_id=issue.issue_id, valid=valid, reason=reason))
        if valid:
            accepted.append(issue)

    renumbered = [
        issue.model_copy(update={"issue_id": f"ISSUE-{index:03d}"})
        for index, issue in enumerate(accepted, start=1)
    ]
    return review.model_copy(update={"issues": renumbered}), checks
