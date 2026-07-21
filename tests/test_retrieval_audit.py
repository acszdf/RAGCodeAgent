import json

from src.retrieval_audit import audit_retrieval
from src.schemas import KnowledgeChunk


class FakeRetriever:
    def query_many(self, queries, top_k):
        return [
            KnowledgeChunk(
                chunk_id="chunk-sql",
                source="security.md",
                section="Prepared statement example",
                text="Bind untrusted values as parameters.",
                distance=0.1,
            )
        ]


def test_audit_accepts_any_predeclared_supporting_section(tmp_path) -> None:
    samples = tmp_path / "samples"
    samples.mkdir()
    (samples / "case.diff").write_text(
        "--- a/store.py\n+++ b/store.py\n@@ -1,1 +1,2 @@\n old\n+cursor.execute(sql)\n",
        encoding="utf-8",
    )
    ground_truth = tmp_path / "ground_truth.json"
    ground_truth.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "sample": "case.diff",
                        "issues": [
                            {
                                "issue_key": "injection",
                                "evidence_source": "security.md",
                                "evidence_sections": [
                                    "General defense",
                                    "Prepared statement example",
                                ],
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    audit = audit_retrieval(FakeRetriever(), samples, ground_truth, top_k=5)

    assert audit["evidence_recall_at_k"] == 1.0
    assert audit["cases"][0]["expected_evidence"][0]["matched_sections"] == [
        "Prepared statement example"
    ]
