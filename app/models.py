"""Data model for a reproducible publication and its artifacts.

A publication is the unit of "science" on the platform. It is not just a paper:
to be publishable it must bundle everything needed to reproduce the result.
Each piece of that bundle is an Artifact tagged with a category.
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


# The artifact categories that make a result reproducible. The first four are
# required to "publish"; environment is strongly recommended.
CATEGORIES = {
    "manuscript": "Manuscript — the write-up of the result (PDF, Markdown, LaTeX).",
    "data": "Data — the datasets the result is based on.",
    "code": "Code — analysis/processing code, or a link to a code repository.",
    "protocol": "Protocol — methods/steps needed to redo the work.",
    "environment": "Environment — dependencies, Dockerfile, lockfiles (recommended).",
}
REQUIRED_CATEGORIES = ["manuscript", "data", "code", "protocol"]


class Publication(Base):
    __tablename__ = "publications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500))
    authors: Mapped[str] = mapped_column(String(500))
    abstract: Mapped[str] = mapped_column(Text, default="")
    license: Mapped[str] = mapped_column(String(100), default="CC-BY-4.0")
    # Optional external link used when code lives in an existing repo (e.g. GitHub).
    code_url: Mapped[str] = mapped_column(String(1000), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    artifacts: Mapped[list["Artifact"]] = relationship(
        back_populates="publication",
        cascade="all, delete-orphan",
    )

    def categories_present(self) -> set[str]:
        present = {a.category for a in self.artifacts}
        if self.code_url:
            present.add("code")
        return present

    def missing_required(self) -> list[str]:
        present = self.categories_present()
        return [c for c in REQUIRED_CATEGORIES if c not in present]

    def is_reproducible(self) -> bool:
        return not self.missing_required()


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    publication_id: Mapped[int] = mapped_column(
        ForeignKey("publications.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(50), index=True)
    original_name: Mapped[str] = mapped_column(String(500))
    stored_path: Mapped[str] = mapped_column(String(1000))
    content_type: Mapped[str] = mapped_column(String(200), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    publication: Mapped["Publication"] = relationship(back_populates="artifacts")


class ProtocolStar(Base):
    """A community endorsement that a publication's protocol works and is
    well-defined. One per anonymous visitor (identified by a cookie) per
    publication — visitors can toggle their star on and off.
    """
    __tablename__ = "protocol_stars"
    __table_args__ = (
        UniqueConstraint("publication_id", "voter_id", name="uq_star_voter"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    publication_id: Mapped[int] = mapped_column(
        ForeignKey("publications.id", ondelete="CASCADE"), index=True
    )
    voter_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
