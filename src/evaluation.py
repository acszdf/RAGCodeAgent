from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any


SUPPORTED_MODES = {"baseline", "rag"}
RUBRIC_VERSION = "2.0"

REQUIRED_COLUMNS = {
    "sample",
    "mode",
    "rubric_version",
    "evaluator_id",
    "evaluation_date",
    "detected_true_issues",
    "total_ground_truth_issues",
    "false_positives",
    "duplicate_findings",
    "recommendation_quality_1_5",
    "overall_review_quality_1_5",
    "severity_correct",
    "severity_assessed",
    "location_exact",
    "location_assessed",
    "unsupported_claims",
    "total_review_claims",
    "valid_citations",
    "total_citations",
    "supported_citations",
    "citation_support_assessed",
    "notes",
}

NONNEGATIVE_INTEGER_COLUMNS = {
    "detected_true_issues",
    "total_ground_truth_issues",
    "false_positives",
    "duplicate_findings",
    "severity_correct",
    "severity_assessed",
    "location_exact",
    "location_assessed",
    "unsupported_claims",
    "total_review_claims",
    "valid_citations",
    "total_citations",
    "supported_citations",
    "citation_support_assessed",
}

_INTEGER_PATTERN = re.compile(r"0|[1-9][0-9]*")



def _normalized_text_bytes(path: Path) -> bytes:
    # Text-mode reads normalize CRLF and CR to LF, keeping provenance hashes
    # stable across Windows and Linux checkouts.
    return path.read_text(encoding="utf-8").encode("utf-8")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(_normalized_text_bytes(path)).hexdigest()


def _sha256_result_files(path: Path) -> str:
    digest = hashlib.sha256()
    files = [
        file_path
        for mode in sorted(SUPPORTED_MODES)
        for file_path in sorted((path / mode).glob("*.json"))
    ]
    for file_path in files:
        relative = file_path.relative_to(path).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        content = _normalized_text_bytes(file_path)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _parse_nonnegative_integer(value: str, column: str, row_number: int) -> int:
    normalized = value.strip()
    if not _INTEGER_PATTERN.fullmatch(normalized):
        raise ValueError(
            f"row {row_number}: {column} must be a non-negative integer, "
            f"got {value!r}"
        )
    return int(normalized)


def _parse_required_score(value: str, column: str, row_number: int) -> int:
    score = _parse_nonnegative_integer(value, column, row_number)
    if not 1 <= score <= 5:
        raise ValueError(f"row {row_number}: {column} must be between 1 and 5")
    return score


def _parse_optional_score(value: str, column: str, row_number: int) -> int | None:
    if not value.strip():
        return None
    return _parse_required_score(value, column, row_number)


def _load_ground_truth_counts(path: Path) -> dict[str, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise ValueError("ground truth must contain a cases list")

    counts: dict[str, int] = {}
    for case in cases:
        sample = case.get("sample")
        issues = case.get("issues")
        if not isinstance(sample, str) or not sample:
            raise ValueError("ground truth case contains an invalid sample name")
        if sample in counts:
            raise ValueError(f"duplicate ground truth sample: {sample}")
        if not isinstance(issues, list):
            raise ValueError(f"ground truth issues must be a list for {sample}")
        counts[sample] = len(issues)
    return counts


def _load_result_facts(results_dir: Path) -> dict[tuple[str, str], dict[str, int]]:
    facts: dict[tuple[str, str], dict[str, int]] = {}
    for mode in sorted(SUPPORTED_MODES):
        mode_dir = results_dir / mode
        if not mode_dir.is_dir():
            raise ValueError(f"missing result directory: {mode_dir}")
        for path in sorted(mode_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            sample = payload.get("sample")
            review = payload.get("review")
            if not isinstance(sample, str) or not sample:
                raise ValueError(f"result file has invalid sample: {path}")
            if payload.get("mode") != mode:
                raise ValueError(f"result mode does not match directory: {path}")
            if Path(sample).stem != path.stem:
                raise ValueError(f"result filename does not match sample: {path}")
            if not isinstance(review, dict) or not isinstance(review.get("issues"), list):
                raise ValueError(f"result file has invalid review.issues: {path}")

            issues = review["issues"]
            total_citations = 0
            for issue in issues:
                citations = issue.get("citations", [])
                if not isinstance(citations, list):
                    raise ValueError(f"result issue has invalid citations: {path}")
                total_citations += len(citations)

            citation_checks = payload.get("citation_checks", [])
            if not isinstance(citation_checks, list):
                raise ValueError(f"result file has invalid citation_checks: {path}")
            if len(citation_checks) != total_citations:
                raise ValueError(
                    f"citation check count does not match citations in review: {path}"
                )
            valid_citations = sum(check.get("valid") is True for check in citation_checks)

            key = (sample, mode)
            if key in facts:
                raise ValueError(f"duplicate result for sample/mode: {sample}/{mode}")
            facts[key] = {
                "total_review_claims": len(issues),
                "total_citations": total_citations,
                "valid_citations": valid_citations,
            }
    return facts


def _validate_row_relationships(row: dict[str, Any], row_number: int) -> None:
    detected = row["detected_true_issues"]
    ground_truth = row["total_ground_truth_issues"]
    false_positives = row["false_positives"]
    duplicates = row["duplicate_findings"]
    claims = row["total_review_claims"]

    if detected > ground_truth:
        raise ValueError(
            f"row {row_number}: detected_true_issues exceeds ground truth count"
        )
    if detected + false_positives + duplicates != claims:
        raise ValueError(
            f"row {row_number}: total_review_claims must equal detected true "
            "issues + false positives + duplicate findings"
        )
    if row["unsupported_claims"] > false_positives:
        raise ValueError(
            f"row {row_number}: unsupported_claims cannot exceed false_positives"
        )

    if row["severity_assessed"] != detected:
        raise ValueError(
            f"row {row_number}: severity_assessed must equal detected_true_issues"
        )
    if row["severity_correct"] > row["severity_assessed"]:
        raise ValueError(
            f"row {row_number}: severity_correct exceeds severity_assessed"
        )

    if row["location_assessed"] != detected:
        raise ValueError(
            f"row {row_number}: location_assessed must equal detected_true_issues"
        )
    if row["location_exact"] > row["location_assessed"]:
        raise ValueError(
            f"row {row_number}: location_exact exceeds location_assessed"
        )

    if row["valid_citations"] > row["total_citations"]:
        raise ValueError(
            f"row {row_number}: valid_citations exceeds total_citations"
        )
    if row["citation_support_assessed"] > row["total_citations"]:
        raise ValueError(
            f"row {row_number}: citation_support_assessed exceeds total_citations"
        )
    if row["supported_citations"] > row["citation_support_assessed"]:
        raise ValueError(
            f"row {row_number}: supported_citations exceeds assessed citations"
        )

    recommendation_quality = row["recommendation_quality_1_5"]
    if detected == 0 and recommendation_quality is not None:
        raise ValueError(
            f"row {row_number}: recommendation quality must be blank when no "
            "ground-truth issue was detected"
        )
    if detected > 0 and recommendation_quality is None:
        raise ValueError(
            f"row {row_number}: recommendation quality is required when a "
            "ground-truth issue was detected"
        )


def aggregate_human_scores(
    score_path: Path,
    ground_truth_path: Path | None = None,
    results_dir: Path | None = None,
) -> dict[str, dict[str, Any]]:
    with score_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"human score file is missing columns: {sorted(missing)}")
        raw_rows = list(reader)
    if not raw_rows:
        raise ValueError("human score file contains no rows")

    rows: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    for row_number, raw_row in enumerate(raw_rows, start=2):
        sample = raw_row["sample"].strip()
        mode = raw_row["mode"].strip()
        if not sample:
            raise ValueError(f"row {row_number}: sample must not be blank")
        if mode not in SUPPORTED_MODES:
            raise ValueError(f"row {row_number}: unsupported mode: {mode!r}")
        if raw_row["rubric_version"].strip() != RUBRIC_VERSION:
            raise ValueError(
                f"row {row_number}: rubric_version must be {RUBRIC_VERSION!r}"
            )
        if not raw_row["evaluator_id"].strip():
            raise ValueError(f"row {row_number}: evaluator_id must not be blank")
        evaluation_date = raw_row["evaluation_date"].strip()
        try:
            date.fromisoformat(evaluation_date)
        except ValueError as exc:
            raise ValueError(
                f"row {row_number}: evaluation_date must be a valid YYYY-MM-DD date"
            ) from exc

        key = (sample, mode)
        if key in seen_keys:
            raise ValueError(f"duplicate score row for sample/mode: {sample}/{mode}")
        seen_keys.add(key)

        parsed: dict[str, Any] = {
            "sample": sample,
            "mode": mode,
            "rubric_version": raw_row["rubric_version"].strip(),
            "evaluator_id": raw_row["evaluator_id"].strip(),
            "evaluation_date": evaluation_date,
            "notes": raw_row["notes"].strip(),
        }
        for column in NONNEGATIVE_INTEGER_COLUMNS:
            parsed[column] = _parse_nonnegative_integer(
                raw_row[column], column, row_number
            )
        parsed["recommendation_quality_1_5"] = _parse_optional_score(
            raw_row["recommendation_quality_1_5"],
            "recommendation_quality_1_5",
            row_number,
        )
        parsed["overall_review_quality_1_5"] = _parse_required_score(
            raw_row["overall_review_quality_1_5"],
            "overall_review_quality_1_5",
            row_number,
        )
        _validate_row_relationships(parsed, row_number)
        rows.append(parsed)

    expected_keys: set[tuple[str, str]] | None = None
    if ground_truth_path is not None:
        ground_truth_counts = _load_ground_truth_counts(ground_truth_path)
        expected_keys = {
            (sample, mode)
            for sample in ground_truth_counts
            for mode in SUPPORTED_MODES
        }
        if seen_keys != expected_keys:
            missing_keys = sorted(expected_keys - seen_keys)
            extra_keys = sorted(seen_keys - expected_keys)
            raise ValueError(
                f"score coverage mismatch; missing={missing_keys}, extra={extra_keys}"
            )
        for row in rows:
            expected_count = ground_truth_counts[row["sample"]]
            if row["total_ground_truth_issues"] != expected_count:
                raise ValueError(
                    f"ground-truth count mismatch for {row['sample']}/{row['mode']}: "
                    f"CSV={row['total_ground_truth_issues']}, "
                    f"JSON={expected_count}"
                )

    if results_dir is not None:
        result_facts = _load_result_facts(results_dir)
        if expected_keys is not None and set(result_facts) != expected_keys:
            missing_keys = sorted(expected_keys - set(result_facts))
            extra_keys = sorted(set(result_facts) - expected_keys)
            raise ValueError(
                f"result coverage mismatch; missing={missing_keys}, extra={extra_keys}"
            )
        for row in rows:
            key = (row["sample"], row["mode"])
            if key not in result_facts:
                raise ValueError(f"missing result JSON for {row['sample']}/{row['mode']}")
            for column, expected_value in result_facts[key].items():
                if row[column] != expected_value:
                    raise ValueError(
                        f"result mismatch for {row['sample']}/{row['mode']} "
                        f"column {column}: CSV={row[column]}, JSON={expected_value}"
                    )

    totals: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "samples": 0,
            "recommendation_scores": [],
            "overall_scores": [],
            **{column: 0 for column in NONNEGATIVE_INTEGER_COLUMNS},
        }
    )
    for row in rows:
        mode_totals = totals[row["mode"]]
        mode_totals["samples"] += 1
        mode_totals["overall_scores"].append(row["overall_review_quality_1_5"])
        if row["recommendation_quality_1_5"] is not None:
            mode_totals["recommendation_scores"].append(
                row["recommendation_quality_1_5"]
            )
        for column in NONNEGATIVE_INTEGER_COLUMNS:
            mode_totals[column] += row[column]

    summary: dict[str, dict[str, Any]] = {}
    for mode in sorted(totals):
        values = totals[mode]
        recommendation_scores = values["recommendation_scores"]
        overall_scores = values["overall_scores"]
        summary[mode] = {
            "samples": values["samples"],
            "issue_recall": {
                "detected": values["detected_true_issues"],
                "ground_truth": values["total_ground_truth_issues"],
                "rate": _rate(
                    values["detected_true_issues"],
                    values["total_ground_truth_issues"],
                ),
            },
            "false_positives": values["false_positives"],
            "duplicate_findings": values["duplicate_findings"],
            "recommendation_quality": {
                "mean": (
                    round(sum(recommendation_scores) / len(recommendation_scores), 2)
                    if recommendation_scores
                    else None
                ),
                "assessed_samples": len(recommendation_scores),
            },
            "overall_review_quality_mean": round(
                sum(overall_scores) / len(overall_scores), 2
            ),
            "unsupported_claim_rate": {
                "unsupported": values["unsupported_claims"],
                "total_claims": values["total_review_claims"],
                "rate": _rate(
                    values["unsupported_claims"], values["total_review_claims"]
                ),
            },
            "severity_accuracy": {
                "correct": values["severity_correct"],
                "assessed": values["severity_assessed"],
                "rate": _rate(
                    values["severity_correct"], values["severity_assessed"]
                ),
            },
            "exact_location_rate": {
                "exact": values["location_exact"],
                "assessed": values["location_assessed"],
                "rate": _rate(values["location_exact"], values["location_assessed"]),
            },
            "citation_extractive_validity": {
                "valid": values["valid_citations"],
                "total": values["total_citations"],
                "rate": _rate(values["valid_citations"], values["total_citations"]),
            },
            "citation_support_rate": {
                "supported": values["supported_citations"],
                "assessed": values["citation_support_assessed"],
                "rate": _rate(
                    values["supported_citations"],
                    values["citation_support_assessed"],
                ),
            },
        }

    summary["_meta"] = {
        "schema_version": 2,
        "rubric_version": RUBRIC_VERSION,
        "evaluation_rows": len(rows),
        "evaluator_ids": sorted({row["evaluator_id"] for row in rows}),
        "evaluation_dates": sorted({row["evaluation_date"] for row in rows}),
        "score_file_sha256": _sha256_file(score_path),
        "ground_truth_cross_validated": ground_truth_path is not None,
        "ground_truth_sha256": (
            _sha256_file(ground_truth_path) if ground_truth_path is not None else None
        ),
        "result_json_cross_validated": results_dir is not None,
        "result_json_manifest_sha256": (
            _sha256_result_files(results_dir) if results_dir is not None else None
        ),
    }
    return summary


def write_summary(summary: dict[str, dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
