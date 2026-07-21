from pathlib import Path

from src.citation_validator import (
    filter_semantically_invalid_issues,
    validate_citations,
    validate_locations,
)
from src.diff_parser import parse_unified_diff
from src.schemas import Citation, KnowledgeChunk, ReviewIssue, ReviewPayload, Severity


def _review(quote: str) -> ReviewPayload:
    return ReviewPayload(
        summary="One issue",
        issues=[
            ReviewIssue(
                issue_id="ISSUE-001",
                file="app/service.py",
                line_start=3,
                line_end=3,
                category="reliability",
                severity=Severity.HIGH,
                confidence=0.95,
                problem="The exception is discarded.",
                suggestion="Log and re-raise it.",
                explanation="The caller receives a false success result.",
                citations=[
                    Citation(
                        source="rules.md",
                        section="Exceptions",
                        chunk_id="chunk-1",
                        quote=quote,
                    )
                ],
            )
        ],
    )


def test_verbatim_citation_is_accepted() -> None:
    chunks = [
        KnowledgeChunk(
            chunk_id="chunk-1",
            source="rules.md",
            section="Exceptions",
            text="Exceptions must not be silently discarded.",
        )
    ]
    assert validate_citations(_review("must not be silently discarded"), chunks)[0].valid


def test_paraphrased_citation_is_rejected() -> None:
    chunks = [
        KnowledgeChunk(
            chunk_id="chunk-1",
            source="rules.md",
            section="Exceptions",
            text="Exceptions must not be silently discarded.",
        )
    ]
    check = validate_citations(_review("Always log every failure"), chunks)[0]
    assert not check.valid
    assert "verbatim" in check.reason


def test_markdown_code_formatting_does_not_change_quote_identity() -> None:
    chunks = [
        KnowledgeChunk(
            chunk_id="chunk-1",
            source="rules.md",
            section="Exceptions",
            text="A lookup may return `None`; handle `None` before attribute access.",
        )
    ]
    review = _review("A lookup may return None; handle None before attribute access.")

    assert validate_citations(review, chunks)[0].valid


def test_location_must_point_to_added_line() -> None:
    parsed = parse_unified_diff(
        "--- a/app/service.py\n+++ b/app/service.py\n@@ -1,2 +1,3 @@\n old\n+new\n tail\n"
    )
    review = _review("anything")
    review.issues[0].line_start = 2
    assert validate_locations(review, parsed)[0].valid
    review.issues[0].line_start = 3
    assert not validate_locations(review, parsed)[0].valid


def test_correct_snake_case_finding_is_filtered() -> None:
    review = _review("anything")
    issue = review.issues[0]
    issue.category = "style"
    issue.problem = "Function name `get_user` uses mixedCase."
    issue.suggestion = "Use lowercase_with_underscores."

    filtered, checks = filter_semantically_invalid_issues(review)

    assert filtered.issues == []
    assert not checks[0].valid
