from src.retriever import KnowledgeRetriever


def test_faiss_retriever_persists_and_queries(tmp_path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "security.md").write_text(
        "# SQL injection\n\nUse parameterized SQL queries for user input.\n",
        encoding="utf-8",
    )
    (docs / "style.md").write_text(
        "# Naming\n\nUse lowercase function names separated by underscores.\n",
        encoding="utf-8",
    )
    index_path = tmp_path / "index"
    retriever = KnowledgeRetriever(index_path)

    assert retriever.rebuild(docs) == 2
    reopened = KnowledgeRetriever(index_path)
    result = reopened.query("SQL injection parameterized query", top_k=1)

    assert reopened.count == 2
    assert result[0].source == "security.md"


def test_multi_query_keeps_top_result_from_each_intent(tmp_path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "rules.md").write_text(
        "# Naming\n\nUse lowercase identifiers.\n\n"
        "# Exceptions\n\nLog exceptions instead of discarding failures.\n",
        encoding="utf-8",
    )
    retriever = KnowledgeRetriever(tmp_path / "index")
    retriever.rebuild(docs)

    result = retriever.query_many(
        ["lowercase identifier naming", "exceptions discarded failures"], top_k=2
    )

    assert {chunk.section for chunk in result} == {"Naming", "Exceptions"}
