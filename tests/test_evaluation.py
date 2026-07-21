import json

import pytest

from src.evaluation import _sha256_file, _sha256_result_files, aggregate_human_scores


HEADER = (
    "sample,mode,rubric_version,evaluator_id,evaluation_date,"
    "detected_true_issues,total_ground_truth_issues,false_positives,"
    "duplicate_findings,recommendation_quality_1_5,overall_review_quality_1_5,"
    "severity_correct,severity_assessed,location_exact,location_assessed,"
    "unsupported_claims,total_review_claims,valid_citations,total_citations,"
    "supported_citations,citation_support_assessed,notes\n"
)


def _write_ground_truth(path) -> None:
    path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "sample": "case.diff",
                        "issues": [{"issue_key": "one"}, {"issue_key": "two"}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def _write_result(path, sample: str, issue_count: int, citation_count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    issues = []
    for index in range(issue_count):
        issues.append(
            {
                "issue_id": f"ISSUE-{index + 1:03d}",
                "citations": [
                    {"chunk_id": f"chunk-{index}-{citation_index}"}
                    for citation_index in range(citation_count if index == 0 else 0)
                ],
            }
        )
    payload = {
        "sample": sample,
        "mode": path.parent.name,
        "review": {"issues": issues},
        "citation_checks": [
            {"valid": True} for _ in range(citation_count)
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_aggregate_human_scores_with_cross_validation(tmp_path) -> None:
    scores = tmp_path / "scores.csv"
    scores.write_text(
        HEADER
        + "case.diff,baseline,2.0,reviewer-1,2026-07-21,1,2,1,0,4,3,1,1,0,1,1,2,0,0,0,0,ok\n"
        + "case.diff,rag,2.0,reviewer-1,2026-07-21,2,2,0,0,5,5,2,2,2,2,0,2,1,1,1,1,ok\n",
        encoding="utf-8",
    )
    ground_truth = tmp_path / "ground_truth.json"
    _write_ground_truth(ground_truth)
    results_dir = tmp_path / "results"
    _write_result(results_dir / "baseline" / "case.json", "case.diff", 2, 0)
    _write_result(results_dir / "rag" / "case.json", "case.diff", 2, 1)

    summary = aggregate_human_scores(scores, ground_truth, results_dir)

    assert summary["baseline"]["issue_recall"]["rate"] == 0.5
    assert summary["baseline"]["unsupported_claim_rate"]["rate"] == 0.5
    assert summary["baseline"]["exact_location_rate"]["rate"] == 0.0
    assert summary["rag"]["citation_extractive_validity"]["rate"] == 1.0
    assert summary["rag"]["citation_support_rate"]["rate"] == 1.0


def test_rejects_fractional_count(tmp_path) -> None:
    scores = tmp_path / "scores.csv"
    scores.write_text(
        HEADER
        + "case.diff,baseline,2.0,reviewer-1,2026-07-21,0.9,1,0,0,,1,0,0,0,0,0,0,0,0,0,0,bad\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="non-negative integer"):
        aggregate_human_scores(scores)


def test_rejects_duplicate_sample_mode(tmp_path) -> None:
    row = (
        "case.diff,baseline,2.0,reviewer-1,2026-07-21,1,1,0,0,4,4,1,1,1,1,0,1,0,0,0,0,ok\n"
    )
    scores = tmp_path / "scores.csv"
    scores.write_text(HEADER + row + row, encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate score row"):
        aggregate_human_scores(scores)


def test_rejects_unreconciled_claim_counts(tmp_path) -> None:
    scores = tmp_path / "scores.csv"
    scores.write_text(
        HEADER
        + "case.diff,baseline,2.0,reviewer-1,2026-07-21,1,1,0,0,4,4,1,1,1,1,0,2,0,0,0,0,bad\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="total_review_claims must equal"):
        aggregate_human_scores(scores)


def test_provenance_hashes_are_independent_of_line_endings(tmp_path) -> None:
    lf_file = tmp_path / "lf.csv"
    crlf_file = tmp_path / "crlf.csv"
    lf_file.write_bytes(b"header\nvalue\n")
    crlf_file.write_bytes(b"header\r\nvalue\r\n")

    lf_results = tmp_path / "lf-results"
    crlf_results = tmp_path / "crlf-results"
    (lf_results / "baseline").mkdir(parents=True)
    (crlf_results / "baseline").mkdir(parents=True)
    (lf_results / "baseline" / "case.json").write_bytes(b'{"value": 1}\n')
    (crlf_results / "baseline" / "case.json").write_bytes(
        b'{"value": 1}\r\n'
    )

    assert _sha256_file(lf_file) == _sha256_file(crlf_file)
    assert _sha256_result_files(lf_results) == _sha256_result_files(crlf_results)
