import re


def compact_text(text: str, limit: int = 6000) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()[:limit]


def split_text_into_chunks(text: str, limit: int = 1200) -> list[str]:
    compacted = compact_text(text, limit=100000)
    if not compacted:
      return []

    sentences = re.findall(r"[^.!?]+[.!?]?", compacted)
    if not sentences:
        return [compacted[:limit]]

    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        part = sentence.strip()
        if not part:
            continue
        projected = part if not current else current + " " + part
        if len(projected) > limit and current:
            chunks.append(current)
            current = part
        else:
            current = projected

    if current:
        chunks.append(current)

    return chunks
