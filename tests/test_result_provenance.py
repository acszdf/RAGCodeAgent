import hashlib
from pathlib import Path

import pytest

from src.reviewer import PROMPT_VERSION
from src.schemas import ReviewRun


ROOT = Path(__file__).resolve().parents[1]
RESULT_PATHS = sorted((ROOT / "experiment/results/baseline").glob("*.json")) + sorted(
    (ROOT / "experiment/results/rag").glob("*.json")
)


@pytest.mark.parametrize("result_path", RESULT_PATHS, ids=lambda path: path.stem)
def test_result_matches_current_sample_and_prompt(result_path: Path) -> None:
    run = ReviewRun.model_validate_json(result_path.read_text(encoding="utf-8"))
    sample_text = (ROOT / "experiment/samples" / run.sample).read_text(
        encoding="utf-8"
    )
    expected_hash = hashlib.sha256(sample_text.encode("utf-8")).hexdigest()

    assert run.sample_sha256 == expected_hash
    assert run.prompt_version == PROMPT_VERSION
