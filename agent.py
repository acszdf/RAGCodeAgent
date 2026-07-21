from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from src.config import Settings
from src.evaluation import aggregate_human_scores, write_summary
from src.experiment_runner import run_experiments, save_review_run
from src.llm_client import (
    LLMConfigurationError,
    LLMResponseError,
    OpenAICompatibleChatModel,
)
from src.retriever import KnowledgeRetriever
from src.retrieval_audit import audit_retrieval, write_retrieval_audit
from src.reviewer import CodeReviewer


def _make_retriever(settings: Settings) -> KnowledgeRetriever:
    return KnowledgeRetriever(persist_path=settings.faiss_path)


def _make_reviewer(settings: Settings, needs_rag: bool) -> CodeReviewer:
    llm = OpenAICompatibleChatModel(settings)
    retriever = _make_retriever(settings) if needs_rag else None
    return CodeReviewer(llm, retriever, settings.retrieval_top_k)


def _project_path(settings: Settings, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else settings.root_dir / path


def command_doctor(settings: Settings, _: argparse.Namespace) -> int:
    report = {
        "python": sys.version.split()[0],
        "root_dir": str(settings.root_dir),
        "docs_dir_exists": settings.docs_dir.exists(),
        "llm_model": settings.llm_model,
        "llm_base_url": settings.llm_base_url,
        "llm_api_key_present": bool(settings.llm_api_key),
        "embedding_provider": "deterministic-tfidf",
        "faiss_path": str(settings.faiss_path),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def command_index(settings: Settings, _: argparse.Namespace) -> int:
    retriever = _make_retriever(settings)
    count = retriever.rebuild(settings.docs_dir)
    print(f"Indexed {count} chunks into {settings.faiss_path}.")
    return 0


def command_audit_retrieval(settings: Settings, args: argparse.Namespace) -> int:
    retriever = _make_retriever(settings)
    audit = audit_retrieval(
        retriever,
        _project_path(settings, args.samples_dir),
        _project_path(settings, args.ground_truth),
        settings.retrieval_top_k,
    )
    output = _project_path(settings, args.output)
    write_retrieval_audit(audit, output)
    print(
        f"Evidence recall@{audit['top_k']}: "
        f"{audit['matched_evidence_count']}/{audit['expected_evidence_count']} "
        f"({audit['evidence_recall_at_k']:.2%})"
    )
    print(f"Saved retrieval audit to {output}")
    return 0


def command_review(settings: Settings, args: argparse.Namespace) -> int:
    reviewer = _make_reviewer(settings, needs_rag=args.mode == "rag")
    diff_path = _project_path(settings, args.diff)
    run = reviewer.review(diff_path, args.mode)
    if args.output:
        output_path = _project_path(settings, args.output)
        save_review_run(run, output_path)
        print(f"Saved review to {output_path}")
    else:
        print(json.dumps(run.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


def command_experiment(settings: Settings, args: argparse.Namespace) -> int:
    modes = ["baseline", "rag"] if args.mode == "both" else [args.mode]
    reviewer = _make_reviewer(settings, needs_rag="rag" in modes)
    outputs = run_experiments(
        reviewer,
        settings.root_dir / "experiment" / "samples",
        settings.root_dir / "experiment" / "results",
        modes,
    )
    for output in outputs:
        print(output.relative_to(settings.root_dir))
    print(f"Completed {len(outputs)} review runs.")
    return 0


def command_evaluate(settings: Settings, args: argparse.Namespace) -> int:
    score_path = _project_path(settings, args.scores)
    ground_truth_path = _project_path(settings, args.ground_truth)
    results_dir = _project_path(settings, args.results_dir)
    output = _project_path(settings, args.output)
    summary = aggregate_human_scores(
        score_path,
        ground_truth_path=ground_truth_path,
        results_dir=results_dir,
    )
    write_summary(summary, output)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Saved aggregate metrics to {output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evidence-grounded code review agent"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="Check local configuration")
    doctor.set_defaults(handler=command_doctor)

    index = subparsers.add_parser("index", help="Rebuild the FAISS knowledge index")
    index.set_defaults(handler=command_index)

    audit = subparsers.add_parser(
        "audit-retrieval", help="Measure evidence recall before calling an LLM"
    )
    audit.add_argument(
        "--output", default="experiment/results/retrieval/audit.json"
    )
    audit.add_argument("--samples-dir", default="experiment/samples")
    audit.add_argument("--ground-truth", default="experiment/ground_truth.json")
    audit.set_defaults(handler=command_audit_retrieval)

    review = subparsers.add_parser("review", help="Review one unified diff")
    review.add_argument("--mode", choices=["baseline", "rag"], required=True)
    review.add_argument("--diff", required=True)
    review.add_argument("--output")
    review.set_defaults(handler=command_review)

    experiment = subparsers.add_parser(
        "experiment", help="Run all experiment samples"
    )
    experiment.add_argument(
        "--mode", choices=["baseline", "rag", "both"], default="both"
    )
    experiment.set_defaults(handler=command_experiment)

    evaluate = subparsers.add_parser(
        "evaluate", help="Aggregate completed human evaluation scores"
    )
    evaluate.add_argument(
        "--scores", default="experiment/human_evaluation.csv"
    )
    evaluate.add_argument(
        "--ground-truth", default="experiment/ground_truth.json"
    )
    evaluate.add_argument(
        "--results-dir", default="experiment/results"
    )
    evaluate.add_argument(
        "--output", default="experiment/results/metrics.json"
    )
    evaluate.set_defaults(handler=command_evaluate)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    settings = Settings.from_env()
    try:
        return args.handler(settings, args)
    except (
        FileNotFoundError,
        RuntimeError,
        ValueError,
        ValidationError,
        LLMConfigurationError,
        LLMResponseError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
