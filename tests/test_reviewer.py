import json
from pathlib import Path

from src.diff_parser import parse_unified_diff
from src.reviewer import CodeReviewer, build_retrieval_query


class FakeChatModel:
    model_name = "fake-test-model"

    def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "summary": "One issue",
            "issues": [
                {
                    "issue_id": "ISSUE-001",
                    "file": "app/pricing.py",
                    "line_start": 1,
                    "line_end": 1,
                    "category": "style",
                    "severity": "low",
                    "confidence": 0.99,
                    "problem": "The function name is not snake_case.",
                    "suggestion": "Rename it to calculate_total.",
                    "explanation": "Python function names conventionally use snake_case.",
                    "citations": [],
                }
            ],
        }
        return json.dumps(payload)


def test_baseline_review_is_structured() -> None:
    root = Path(__file__).resolve().parents[1]
    reviewer = CodeReviewer(FakeChatModel())
    run = reviewer.review(root / "experiment/samples/case_01_naming.diff", "baseline")

    assert run.mode == "baseline"
    assert run.review.issues[0].issue_id == "ISSUE-001"
    assert run.location_checks[0].valid
    assert run.retrieved_chunks == []


def test_retrieval_query_uses_generic_concepts_not_document_headings() -> None:
    root = Path(__file__).resolve().parents[1]
    raw = (root / "experiment/samples/case_03_sql_injection.diff").read_text(
        encoding="utf-8"
    )
    query = build_retrieval_query(parse_unified_diff(raw))

    assert "SQL injection prevention" in query
    assert "Primary Defenses" not in query
    assert "Defense Option 1" not in query
    assert "Missing entity handling" not in query
    assert "HTTP layer boundary" not in query
