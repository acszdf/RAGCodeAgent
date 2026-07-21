from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from .schemas import KnowledgeChunk


SUPPORTED_SUFFIXES = {".md", ".rst", ".txt"}
MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
RST_UNDERLINE_RE = re.compile(r"^[=\-~^\"'`:+*#<>_]{3,}\s*$")


@dataclass(frozen=True)
class Section:
    title: str
    text: str


def _read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"cannot decode {path}")


def _sections(text: str, fallback_title: str) -> list[Section]:
    lines = text.splitlines()
    output: list[Section] = []
    title = fallback_title
    body: list[str] = []

    def flush() -> None:
        content = "\n".join(body).strip()
        if content:
            output.append(Section(title=title, text=content))

    index = 0
    while index < len(lines):
        markdown = MARKDOWN_HEADING_RE.match(lines[index])
        is_rst = (
            index + 1 < len(lines)
            and lines[index].strip()
            and RST_UNDERLINE_RE.match(lines[index + 1]) is not None
        )
        if markdown or is_rst:
            flush()
            body = []
            title = markdown.group(2).strip() if markdown else lines[index].strip()
            index += 2 if is_rst else 1
            continue
        body.append(lines[index])
        index += 1
    flush()
    return output


def _split_section(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            step = max(1, max_chars - overlap_chars)
            chunks.extend(
                paragraph[start : start + max_chars]
                for start in range(0, len(paragraph), step)
            )
            continue
        candidate = f"{current}\n\n{paragraph}".strip()
        if current and len(candidate) > max_chars:
            chunks.append(current)
            overlap = current[-overlap_chars:] if overlap_chars else ""
            current = f"{overlap}\n\n{paragraph}".strip()
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks

def load_knowledge_chunks(
    docs_dir: Path,
    *,
    max_chars: int = 1200,
    overlap_chars: int = 120,
) -> list[KnowledgeChunk]:
    if not docs_dir.exists():
        raise FileNotFoundError(f"knowledge directory does not exist: {docs_dir}")

    chunks: list[KnowledgeChunk] = []
    for path in sorted(docs_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        source = path.relative_to(docs_dir).as_posix()
        text = _read_text(path)
        for section in _sections(text, path.stem):
            for part in _split_section(section.text, max_chars, overlap_chars):
                digest = hashlib.sha256(
                    f"{source}\0{section.title}\0{part}".encode("utf-8")
                ).hexdigest()[:16]
                chunks.append(
                    KnowledgeChunk(
                        chunk_id=f"chunk-{digest}",
                        source=source,
                        section=section.title,
                        text=part,
                    )
                )
    if not chunks:
        raise ValueError(f"no supported knowledge documents found in {docs_dir}")
    return chunks
