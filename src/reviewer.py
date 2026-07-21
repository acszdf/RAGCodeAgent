from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from .citation_validator import (
    filter_semantically_invalid_issues,
    validate_citations,
    validate_locations,
)
from .diff_parser import ParsedDiff, parse_unified_diff
from .llm_client import ChatModel, LLMResponseError, parse_json_response
from .retriever import KnowledgeRetriever
from .schemas import KnowledgeChunk, ReviewPayload, ReviewRun


PROMPT_VERSION = "2026-07-21.1"
SYSTEM_PROMPT = """You are a precise senior code reviewer.
Review only defects introduced by the supplied Git diff. Do not report pre-existing code,
missing context, or purely subjective preferences as definite defects. Prefer a small number
of high-confidence findings. Return only one JSON object matching the supplied schema."""


def build_retrieval_queries(parsed: ParsedDiff) -> list[str]:
    raw = parsed.raw.lower()
    topics: list[str] = []
    signals = {
        "Python function variable parameter naming style lowercase underscore": [
            "def ",
            "class ",
        ],
        "SQL injection prevention untrusted input parameterized query prepared statement": [
            "execute(",
            "select ",
            "insert ",
            "update ",
            "delete ",
            "cursor",
        ],
        "database lookup missing result None check before attribute access": [
            ".first()",
            ".get(",
            "find_by_",
            "none",
        ],
        "web route architecture service repository layer dependency boundary": [
            "@app.route",
            "@bp.",
            "repository",
            "routes/",
        ],
        "error failure logging observability swallowed exceptions status": [
            "except ",
            "pass",
            "raise ",
        ],
    }
    for topic, needles in signals.items():
        if any(needle in raw for needle in needles):
            topics.append(topic)
    code_tokens = " ".join(
        token
        for token in parsed.compact_context().replace("_", " ").split()
        if token.isidentifier()
    )
    if topics:
        return topics
    fallback = "Python code change review defects security reliability maintainability"
    if code_tokens:
        fallback += "\nCode identifiers and operations: " + code_tokens[:800]
    return [fallback]


def build_retrieval_query(parsed: ParsedDiff) -> str:
    return "\n\n--- query ---\n\n".join(build_retrieval_queries(parsed))


def retrieve_knowledge(
    retriever: KnowledgeRetriever,
    parsed: ParsedDiff,
    top_k: int,
) -> tuple[str, list[KnowledgeChunk]]:
    queries = build_retrieval_queries(parsed)
    return build_retrieval_query(parsed), retriever.query_many(queries, top_k)


def _render_knowledge(chunks: list[KnowledgeChunk]) -> str:
    blocks: list[str] = []
    for chunk in chunks:
        blocks.append(
            "\n".join(
                [
                    f"[chunk_id={chunk.chunk_id}]",
                    f"source={chunk.source}",
                    f"section={chunk.section}",
                    "content:",
                    chunk.text,
                ]
            )
        )
    return "\n\n---\n\n".join(blocks)


def build_review_prompt(
    parsed: ParsedDiff,
    mode: str,
    retrieved_chunks: list[KnowledgeChunk],
) -> str:
    schema = json.dumps(ReviewPayload.model_json_schema(), ensure_ascii=False, indent=2)
    evidence_rules = (
        "Set citations to an empty array for every issue. Do not claim that a named standard "
        "or project rule requires something because no knowledge documents are supplied."
        if mode == "baseline"
        else "Use only the knowledge chunks below as external evidence. When a finding relies "
        "on a standard or project rule, cite it with the exact source, section, chunk_id, and a "
        "short verbatim quote. Never invent or paraphrase a quote. A code-local correctness bug "
        "may have an empty citations array when no retrieved chunk supports it. Mandatory "
        "language such as 'must not' or 'prohibited' in project-design.md is a binding local "
        "constraint: report a direct violation as architecture or maintainability, not as a "
        "subjective preference. Never report a naming violation when the identifier already "
        "uses lowercase words separated by underscores."
    )
    knowledge = (
        "No external knowledge is available in baseline mode."
        if mode == "baseline"
        else _render_knowledge(retrieved_chunks)
    )
    return f"""Review mode: {mode}

Rules:
1. Review only added lines shown with a '+' marker.
2. Use the FILE path and numeric new-line labels exactly as supplied.
3. Report one root cause per issue. Do not duplicate findings.
4. Severity meanings: critical = immediate compromise/data loss; high = likely serious runtime
   or security failure; medium = conditional defect or important design violation; low = style
   or maintainability problem with limited runtime impact.
5. Confidence below 0.70 should normally be omitted.
6. {evidence_rules}
7. issue_id values must be sequential: ISSUE-001, ISSUE-002, ...
8. If no defensible issues exist, return an empty issues array.

Required JSON schema:
{schema}

External knowledge:
{knowledge}

Git diff with explicit new-line labels:
{parsed.compact_context()}
"""


class CodeReviewer:
    def __init__(
        self,
        llm: ChatModel,
        retriever: KnowledgeRetriever | None = None,
        top_k: int = 5,
    ) -> None:
        self.llm = llm
        self.retriever = retriever
        self.top_k = top_k

    def _generate_valid_review(
        self,
        prompt: str,
        raw_attempts: list[str],
    ) -> ReviewPayload:
        current_prompt = prompt
        for attempt in range(2):
            raw_response = self.llm.complete_json(SYSTEM_PROMPT, current_prompt)
            raw_attempts.append(raw_response)
            try:
                return ReviewPayload.model_validate(parse_json_response(raw_response))
            except (ValidationError, LLMResponseError) as exc:
                if attempt == 1:
                    raise
                current_prompt = f"""Your previous response failed JSON validation.
Return only a corrected JSON object. Preserve only defensible findings from the original
review and obey the schema and evidence rules in the original task.

Validation error:
{exc}

Original task:
{prompt}

Invalid response:
{raw_response}
"""
        raise LLMResponseError("model did not produce a valid review")

    def review(self, diff_path: Path, mode: str) -> ReviewRun:
        if mode not in {"baseline", "rag"}:
            raise ValueError("mode must be 'baseline' or 'rag'")
        raw_diff = diff_path.read_text(encoding="utf-8")
        parsed = parse_unified_diff(raw_diff)

        retrieval_query: str | None = None
        chunks: list[KnowledgeChunk] = []
        if mode == "rag":
            if self.retriever is None:
                raise RuntimeError("RAG mode requires a knowledge retriever")
            retrieval_query, chunks = retrieve_knowledge(
                self.retriever, parsed, self.top_k
            )

        prompt = build_review_prompt(parsed, mode, chunks)
        raw_attempts: list[str] = []
        draft = self._generate_valid_review(prompt, raw_attempts)
        audit_prompt = f"""Perform a final quality audit of a draft code review.

Use the original task, diff, schema, and evidence rules below. Return the complete corrected
JSON review, not commentary about the draft.

Audit requirements:
1. Remove any finding that says the referenced code is already correct, says there is no
   issue, or tells itself to remove the finding.
2. Remove speculative findings that require context absent from the diff.
3. Merge findings with the same root cause and keep the most precise added-line location.
4. Verify that every named identifier actually violates the stated naming rule.
5. Keep all clear correctness and security defects introduced by the diff.
6. In RAG mode, include clear violations of retrieved project rules when the diff directly
   demonstrates them, and attach only verbatim citations from the supplied chunks.
7. Renumber issue_id values sequentially after editing.

Original task:
{prompt}

Draft review:
{json.dumps(draft.model_dump(mode="json"), ensure_ascii=False, indent=2)}
"""
        review = self._generate_valid_review(audit_prompt, raw_attempts)
        review, quality_checks = filter_semantically_invalid_issues(review)
        return ReviewRun(
            mode=mode,
            model=self.llm.model_name,
            prompt_version=PROMPT_VERSION,
            created_at=datetime.now(timezone.utc).isoformat(),
            sample=diff_path.name,
            sample_sha256=hashlib.sha256(raw_diff.encode("utf-8")).hexdigest(),
            retrieval_query=retrieval_query,
            prompt=prompt,
            raw_response=raw_attempts[-1],
            raw_attempts=raw_attempts,
            review=review,
            retrieved_chunks=chunks,
            citation_checks=validate_citations(review, chunks),
            location_checks=validate_locations(review, parsed),
            quality_checks=quality_checks,
        )
