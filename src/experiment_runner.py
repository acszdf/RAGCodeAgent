from __future__ import annotations

import json
from pathlib import Path

from .reviewer import CodeReviewer
from .schemas import ReviewRun


def save_review_run(run: ReviewRun, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(run.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def run_experiments(
    reviewer: CodeReviewer,
    samples_dir: Path,
    results_dir: Path,
    modes: list[str],
) -> list[Path]:
    samples = sorted(samples_dir.glob("*.diff"))
    if not samples:
        raise FileNotFoundError(f"no .diff samples found in {samples_dir}")
    outputs: list[Path] = []
    for sample in samples:
        for mode in modes:
            run = reviewer.review(sample, mode)
            output = results_dir / mode / f"{sample.stem}.json"
            save_review_run(run, output)
            outputs.append(output)
    return outputs
