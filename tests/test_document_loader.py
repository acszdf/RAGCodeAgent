from src.document_loader import load_knowledge_chunks


def test_loader_keeps_source_and_section(tmp_path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "rules.md").write_text(
        "# Demo\n\n## Error handling\n\nNever discard exceptions silently.\n",
        encoding="utf-8",
    )

    chunks = load_knowledge_chunks(docs, max_chars=200, overlap_chars=0)

    assert len(chunks) == 1
    assert chunks[0].source == "rules.md"
    assert chunks[0].section == "Error handling"
    assert chunks[0].text == "Never discard exceptions silently."
