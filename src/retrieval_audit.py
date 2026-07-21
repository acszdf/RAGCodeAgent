from __future__ import annotations

import json
from pathlib import Path

from .diff_parser import parse_unified_diff
from .retriever import KnowledgeRetriever
from .reviewer import retrieve_knowledge


def _evidence_target(issue: dict) -> tuple[str, list[str]]:
    sections = issue.get("evidence_sections")
    if sections is None:
        sections = [issue["evidence_section"]]
    return issue["evidence_source"], sections


def audit_retrieval(
    retriever: KnowledgeRetriever,
    samples_dir: Path,
    ground_truth_path: Path,
    top_k: int,
) -> dict:
    ground_truth = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    cases: list[dict] = []
    matched = 0
    expected_total = 0

    for case in ground_truth["cases"]:
        sample_path = samples_dir / case["sample"]
        parsed = parse_unified_diff(sample_path.read_text(encoding="utf-8"))
        query, chunks = retrieve_knowledge(retriever, parsed, top_k)
        evidence_results: list[dict] = []
        for issue in case["issues"]:
            if not issue.get("evidence_source"):
                continue
            source, sections = _evidence_target(issue)
            matched_sections = [
                section
                for section in sections
                if any(
                    chunk.source == source and chunk.section == section
                    for chunk in chunks
                )
            ]
            evidence_results.append(
                {
                    "issue_key": issue["issue_key"],
                    "source": source,
                    "acceptable_sections": sections,
                    "matched_sections": matched_sections,
                    "hit": bool(matched_sections),
                }
            )
        matched += sum(1 for item in evidence_results if item["hit"])
        expected_total += len(evidence_results)
        cases.append(
            {
                "sample": case["sample"],
                "query": query,
                "expected_evidence": evidence_results,
                "retrieved_chunks": [
                    {
                        "rank": rank,
                        "chunk_id": chunk.chunk_id,
                        "source": chunk.source,
                        "section": chunk.section,
                        "distance": round(chunk.distance or 0.0, 6),
                        "text": chunk.text,
                    }
                    for rank, chunk in enumerate(chunks, start=1)
                ],
            }
        )

    return {
        "top_k": top_k,
        "expected_evidence_count": expected_total,
        "matched_evidence_count": matched,
        "evidence_recall_at_k": round(matched / expected_total, 4)
        if expected_total
        else None,
        "cases": cases,
    }


def write_retrieval_audit(audit: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
