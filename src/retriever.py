from __future__ import annotations

import json
import math
import re
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

import faiss
import numpy as np

from .document_loader import load_knowledge_chunks
from .schemas import KnowledgeChunk


def _terms(text: str) -> list[str]:
    expanded = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text).replace("_", " ")
    words = re.findall(r"[A-Za-z][A-Za-z0-9-]*|[\u4e00-\u9fff]", expanded.lower())
    return words + [f"{left}::{right}" for left, right in zip(words, words[1:])]


class TfidfEmbeddingFunction:
    """Small deterministic TF-IDF encoder persisted together with the FAISS index."""

    def __init__(
        self,
        vocabulary: dict[str, int] | None = None,
        idf: list[float] | None = None,
    ) -> None:
        self.vocabulary = vocabulary or {}
        self.idf = np.asarray(idf or [], dtype="float32")

    def fit(self, documents: Sequence[str]) -> "TfidfEmbeddingFunction":
        document_frequency: Counter[str] = Counter()
        for document in documents:
            document_frequency.update(set(_terms(document)))
        ordered_terms = sorted(document_frequency)
        self.vocabulary = {term: index for index, term in enumerate(ordered_terms)}
        count = len(documents)
        self.idf = np.asarray(
            [
                math.log((1 + count) / (1 + document_frequency[term])) + 1
                for term in ordered_terms
            ],
            dtype="float32",
        )
        return self

    def transform(self, documents: Sequence[str]) -> np.ndarray:
        if not self.vocabulary:
            raise RuntimeError("TF-IDF encoder has not been fitted")
        vectors = np.zeros((len(documents), len(self.vocabulary)), dtype="float32")
        for row, document in enumerate(documents):
            counts = Counter(_terms(document))
            for term, frequency in counts.items():
                column = self.vocabulary.get(term)
                if column is not None:
                    vectors[row, column] = (1 + math.log(frequency)) * self.idf[column]
        faiss.normalize_L2(vectors)
        return vectors

    def to_dict(self) -> dict:
        return {"vocabulary": self.vocabulary, "idf": self.idf.tolist()}

    @classmethod
    def from_dict(cls, value: dict) -> "TfidfEmbeddingFunction":
        return cls(vocabulary=value["vocabulary"], idf=value["idf"])


class KnowledgeRetriever:
    INDEX_FILE = "knowledge.faiss"
    METADATA_FILE = "chunks.json"
    VECTORIZER_FILE = "vectorizer.json"

    def __init__(self, persist_path: Path) -> None:
        self.persist_path = persist_path
        self.persist_path.mkdir(parents=True, exist_ok=True)
        self._embed = TfidfEmbeddingFunction()
        self._index: faiss.Index | None = None
        self._chunks: list[KnowledgeChunk] = []
        self._incomplete = False
        self._load_if_present()

    def _load_if_present(self) -> None:
        paths = [
            self.persist_path / self.INDEX_FILE,
            self.persist_path / self.METADATA_FILE,
            self.persist_path / self.VECTORIZER_FILE,
        ]
        if not any(path.exists() for path in paths):
            return
        if not all(path.exists() for path in paths):
            self._incomplete = True
            return
        serialized = np.frombuffer(paths[0].read_bytes(), dtype=np.uint8)
        self._index = faiss.deserialize_index(serialized)
        records = json.loads(paths[1].read_text(encoding="utf-8"))
        self._chunks = [KnowledgeChunk.model_validate(item) for item in records]
        vectorizer = json.loads(paths[2].read_text(encoding="utf-8"))
        self._embed = TfidfEmbeddingFunction.from_dict(vectorizer)
        if self._index.ntotal != len(self._chunks):
            raise RuntimeError("FAISS index and chunk metadata counts do not match")

    @property
    def count(self) -> int:
        return int(self._index.ntotal) if self._index is not None else 0

    @staticmethod
    def _chunk_document(chunk: KnowledgeChunk) -> str:
        return f"{chunk.source}\n{chunk.section}\n{chunk.text}"

    def rebuild(self, docs_dir: Path) -> int:
        chunks = load_knowledge_chunks(docs_dir)
        documents = [self._chunk_document(chunk) for chunk in chunks]
        self._embed = TfidfEmbeddingFunction().fit(documents)
        vectors = self._embed.transform(documents)
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)

        self._index = index
        self._chunks = chunks
        self._incomplete = False
        serialized = faiss.serialize_index(index)
        (self.persist_path / self.INDEX_FILE).write_bytes(serialized.tobytes())
        (self.persist_path / self.METADATA_FILE).write_text(
            json.dumps(
                [chunk.model_dump(mode="json") for chunk in chunks],
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (self.persist_path / self.VECTORIZER_FILE).write_text(
            json.dumps(self._embed.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return len(chunks)

    def query(self, text: str, top_k: int) -> list[KnowledgeChunk]:
        if self._index is None or not self._chunks:
            state = "incomplete" if self._incomplete else "empty"
            raise RuntimeError(
                f"knowledge index is {state}; run `python agent.py index`"
            )
        query_vector = self._embed.transform([text])
        scores, indices = self._index.search(query_vector, min(top_k, self.count))
        results: list[KnowledgeChunk] = []
        for score, index in zip(scores[0], indices[0], strict=True):
            if index < 0:
                continue
            chunk = self._chunks[int(index)].model_copy(deep=True)
            chunk.distance = float(1.0 - score)
            results.append(chunk)
        return results

    def query_many(self, queries: Sequence[str], top_k: int) -> list[KnowledgeChunk]:
        if not queries:
            raise ValueError("at least one retrieval query is required")
        candidates: dict[str, tuple[float, float, int, KnowledgeChunk]] = {}
        seen_order = 0
        for query in queries:
            for rank, chunk in enumerate(self.query(query, top_k), start=1):
                reciprocal_rank = 1.0 / rank
                distance = chunk.distance if chunk.distance is not None else float("inf")
                previous = candidates.get(chunk.chunk_id)
                if previous is None:
                    candidates[chunk.chunk_id] = (
                        reciprocal_rank,
                        distance,
                        seen_order,
                        chunk,
                    )
                    seen_order += 1
                elif reciprocal_rank > previous[0] or (
                    reciprocal_rank == previous[0] and distance < previous[1]
                ):
                    candidates[chunk.chunk_id] = (
                        reciprocal_rank,
                        distance,
                        previous[2],
                        chunk,
                    )
        ranked = sorted(
            candidates.values(),
            key=lambda item: (-item[0], item[1], item[2]),
        )
        return [item[3] for item in ranked[:top_k]]
