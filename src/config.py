from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]


def _resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


@dataclass(frozen=True)
class Settings:
    root_dir: Path
    docs_dir: Path
    faiss_path: Path
    retrieval_top_k: int
    llm_api_key: str | None
    llm_base_url: str
    llm_model: str
    llm_temperature: float
    llm_timeout_seconds: float

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(ROOT_DIR / ".env")
        api_key = (
            os.getenv("LLM_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("DEEPSEEK_API_KEY")
            or os.getenv("ZHIPUAI_API_KEY")
        )
        return cls(
            root_dir=ROOT_DIR,
            docs_dir=ROOT_DIR / "docs" / "knowledge",
            faiss_path=_resolve_path(os.getenv("FAISS_PATH", ".faiss")),
            retrieval_top_k=int(os.getenv("RETRIEVAL_TOP_K", "5")),
            llm_api_key=api_key,
            llm_base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
            llm_model=os.getenv("LLM_MODEL", "gpt-4.1-mini"),
            llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0")),
            llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "120")),
        )
