"""Extract text from an uploaded PDF manuscript.

Parsing is done on view and cached per process (keyed by stored path) so we only
pay the cost once per file. Returns a structured result the template can render.
"""
from pathlib import Path

from pypdf import PdfReader

_cache: dict[str, dict] = {}


def extract_text(path: Path):
    """Return {"pages": int, "text": str} for a PDF, or {"error": str}.

    Never raises — a malformed/encrypted PDF degrades to an error message so the
    page still renders the embedded viewer.
    """
    key = str(path)
    if key in _cache:
        return _cache[key]

    try:
        reader = PdfReader(str(path))
        chunks = []
        for page in reader.pages:
            chunks.append(page.extract_text() or "")
        text = "\n\n".join(chunks).strip()
        result = {"pages": len(reader.pages), "text": text}
    except Exception as e:  # pypdf raises a variety of types; keep the page alive
        result = {"error": f"Could not parse PDF: {e}"}

    _cache[key] = result
    return result
