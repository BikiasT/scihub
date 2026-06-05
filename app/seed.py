"""Seed an example publication that links a GitHub repo as its code.

Run once:  ./.venv/bin/python -m app.seed
Idempotent — it won't create a duplicate if the example already exists.
"""
from sqlalchemy import select

from .db import SessionLocal, init_db
from .models import Artifact, Publication
from .storage import new_slug, save_upload

EXAMPLE_CODE_URL = "https://github.com/BikiasT/ReverseZoo"
EXAMPLE_TITLE = "ReverseZoo: an example reproducible publication"


def run():
    init_db()
    db = SessionLocal()
    try:
        existing = db.scalar(
            select(Publication).where(Publication.title == EXAMPLE_TITLE)
        )
        if existing:
            print(f"Example already exists: /publications/{existing.slug}")
            return

        slug = new_slug()
        pub = Publication(
            slug=slug,
            title=EXAMPLE_TITLE,
            authors="BikiasT",
            abstract=(
                "Example publication demonstrating the GitHub code connection. "
                "The code artifact is linked to a live repository rather than "
                "uploaded, so its metadata is fetched from GitHub on view."
            ),
            license="CC-BY-4.0",
            code_url=EXAMPLE_CODE_URL,
        )
        db.add(pub)
        db.flush()

        # Minimal accompanying artifacts so the bundle is meaningful.
        for category, name, content in [
            ("manuscript", "manuscript.md",
             b"# ReverseZoo\n\nExample manuscript. See the linked GitHub repo for code.\n"),
            ("data", "README.txt",
             b"Place datasets here. This example uses code from GitHub.\n"),
            ("protocol", "protocol.md",
             b"# Protocol\n\n1. Clone the repo.\n2. Follow its README to reproduce.\n"),
        ]:
            rel = save_upload(slug, category, name, content)
            db.add(Artifact(
                publication_id=pub.id, category=category, original_name=name,
                stored_path=str(rel), content_type="text/plain", size_bytes=len(content),
            ))

        db.commit()
        print(f"Created example: /publications/{slug}")
    finally:
        db.close()


if __name__ == "__main__":
    run()
