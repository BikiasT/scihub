"""FastAPI app: upload everything needed to reproduce a publication.

Routes
  GET  /                       list publications
  GET  /new                    upload form
  POST /publications           create a publication + its artifact files
  GET  /publications/{slug}    detail + reproducibility checklist
  GET  /publications/{slug}/files/{artifact_id}   download a file
"""
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import get_db, init_db
from .github import fetch_repo
from .models import (
    CATEGORIES,
    REQUIRED_CATEGORIES,
    Artifact,
    ProtocolStar,
    Publication,
)
from .pdfparse import extract_text
from .storage import absolute_path, new_slug, save_upload

BASE_DIR = Path(__file__).resolve().parent
VOTER_COOKIE = "scihub_voter"
app = FastAPI(title="SciHub — reproducible publications")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def _star_count(db: Session, publication_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(ProtocolStar)
        .where(ProtocolStar.publication_id == publication_id)
    ) or 0


@app.on_event("startup")
def _startup():
    init_db()


def _human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{int(n)} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


templates.env.filters["filesize"] = lambda n: _human_size(int(n))


@app.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    pubs = db.scalars(select(Publication).order_by(Publication.created_at.desc())).all()
    # Protocol star counts, keyed by publication id, for the list cards.
    rows = db.execute(
        select(ProtocolStar.publication_id, func.count())
        .group_by(ProtocolStar.publication_id)
    ).all()
    stars = {pid: count for pid, count in rows}
    return templates.TemplateResponse(
        "index.html", {"request": request, "publications": pubs, "stars": stars}
    )


@app.get("/new", response_class=HTMLResponse)
def new_form(request: Request):
    return templates.TemplateResponse(
        "new.html",
        {"request": request, "categories": CATEGORIES, "required": REQUIRED_CATEGORIES},
    )


@app.post("/publications")
async def create_publication(
    request: Request,
    title: str = Form(...),
    authors: str = Form(...),
    abstract: str = Form(""),
    license: str = Form("CC-BY-4.0"),
    code_url: str = Form(""),
    manuscript: list[UploadFile] = [],  # noqa: B006 - FastAPI handles this
    data: list[UploadFile] = [],  # noqa: B006
    code: list[UploadFile] = [],  # noqa: B006
    protocol: list[UploadFile] = [],  # noqa: B006
    environment: list[UploadFile] = [],  # noqa: B006
    db: Session = Depends(get_db),
):
    slug = new_slug()
    pub = Publication(
        slug=slug,
        title=title.strip(),
        authors=authors.strip(),
        abstract=abstract.strip(),
        license=license.strip() or "CC-BY-4.0",
        code_url=code_url.strip(),
    )
    db.add(pub)
    db.flush()  # assign pub.id

    uploads = {
        "manuscript": manuscript,
        "data": data,
        "code": code,
        "protocol": protocol,
        "environment": environment,
    }
    for category, files in uploads.items():
        for f in files:
            if not f or not f.filename:
                continue
            content = await f.read()
            if not content:
                continue
            rel = save_upload(slug, category, f.filename, content)
            db.add(
                Artifact(
                    publication_id=pub.id,
                    category=category,
                    original_name=f.filename,
                    stored_path=str(rel),
                    content_type=f.content_type or "",
                    size_bytes=len(content),
                )
            )

    db.commit()
    return RedirectResponse(url=f"/publications/{slug}", status_code=303)


@app.get("/publications/{slug}", response_class=HTMLResponse)
def detail(slug: str, request: Request, db: Session = Depends(get_db)):
    pub = db.scalar(select(Publication).where(Publication.slug == slug))
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")

    by_category: dict[str, list[Artifact]] = {c: [] for c in CATEGORIES}
    for a in pub.artifacts:
        by_category.setdefault(a.category, []).append(a)

    # If code is linked to a GitHub repo, pull live metadata for the code card.
    github = fetch_repo(pub.code_url) if pub.code_url else None

    # Parse text out of manuscript PDFs so the content shows in the main pane.
    parsed: dict[int, dict] = {}
    for a in by_category.get("manuscript", []):
        if a.original_name.lower().endswith(".pdf"):
            parsed[a.id] = extract_text(absolute_path(a.stored_path))

    # Protocol stars: total count + whether this visitor has starred.
    voter = request.cookies.get(VOTER_COOKIE)
    starred = bool(voter) and db.scalar(
        select(ProtocolStar.id).where(
            ProtocolStar.publication_id == pub.id, ProtocolStar.voter_id == voter
        )
    ) is not None

    return templates.TemplateResponse(
        "detail.html",
        {
            "request": request,
            "pub": pub,
            "categories": CATEGORIES,
            "required": REQUIRED_CATEGORIES,
            "by_category": by_category,
            "present": pub.categories_present(),
            "missing": pub.missing_required(),
            "github": github,
            "parsed": parsed,
            "stars": _star_count(db, pub.id),
            "starred": starred,
        },
    )


@app.post("/publications/{slug}/star")
def toggle_star(slug: str, request: Request, db: Session = Depends(get_db)):
    """Toggle the current visitor's protocol star for a publication."""
    pub = db.scalar(select(Publication).where(Publication.slug == slug))
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")

    voter = request.cookies.get(VOTER_COOKIE)
    new_voter = None
    if not voter:
        voter = new_voter = secrets.token_hex(16)

    existing = db.scalar(
        select(ProtocolStar).where(
            ProtocolStar.publication_id == pub.id, ProtocolStar.voter_id == voter
        )
    )
    if existing:
        db.delete(existing)
        starred = False
    else:
        db.add(ProtocolStar(publication_id=pub.id, voter_id=voter))
        starred = True
    db.commit()

    resp = JSONResponse({"stars": _star_count(db, pub.id), "starred": starred})
    if new_voter:
        # 1-year cookie so a returning visitor keeps the same identity.
        resp.set_cookie(
            VOTER_COOKIE, new_voter, max_age=31536000, httponly=True, samesite="lax"
        )
    return resp


@app.get("/publications/{slug}/files/{artifact_id}")
def download(
    slug: str, artifact_id: int, inline: bool = False, db: Session = Depends(get_db)
):
    art = db.scalar(
        select(Artifact)
        .join(Publication)
        .where(Publication.slug == slug, Artifact.id == artifact_id)
    )
    if not art:
        raise HTTPException(status_code=404, detail="File not found")
    path = absolute_path(art.stored_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File missing on disk")
    # inline=1 lets the browser render the file in an <iframe>/preview instead of
    # forcing a download (used for the manuscript preview pane).
    headers = None
    if inline:
        headers = {"Content-Disposition": f'inline; filename="{art.original_name}"'}
        return FileResponse(
            path,
            media_type=art.content_type or "application/octet-stream",
            headers=headers,
        )
    return FileResponse(
        path, filename=art.original_name, media_type=art.content_type or "application/octet-stream"
    )
