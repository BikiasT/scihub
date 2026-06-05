"""On-disk storage for uploaded artifact files.

Files live under storage/<publication-slug>/<category>/<filename>. We keep the
original filename but sanitize it and avoid clobbering existing files.
"""
import re
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def new_slug() -> str:
    return secrets.token_hex(5)  # 10 hex chars


def _safe_name(name: str) -> str:
    name = Path(name).name  # strip any path components
    name = _SAFE.sub("_", name).strip("._")
    return name or "file"


def save_upload(slug: str, category: str, original_name: str, data: bytes) -> Path:
    """Write bytes to disk and return the path relative to STORAGE_DIR."""
    dest_dir = STORAGE_DIR / slug / category
    dest_dir.mkdir(parents=True, exist_ok=True)

    name = _safe_name(original_name)
    dest = dest_dir / name
    # Avoid overwriting an existing file with the same name.
    if dest.exists():
        stem, suffix = dest.stem, dest.suffix
        dest = dest_dir / f"{stem}-{secrets.token_hex(3)}{suffix}"

    dest.write_bytes(data)
    return dest.relative_to(STORAGE_DIR)


def absolute_path(stored_path: str) -> Path:
    return STORAGE_DIR / stored_path
