"""project.yaml read/write and validation.

See REWRITE-PLAN.md §6 for the schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class BookEntry:
    name: str
    pov: str | None = None
    story_time_range: list[int] | None = None
    status: str = "seed"

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name}
        if self.pov is not None:
            d["pov"] = self.pov
        if self.story_time_range is not None:
            d["story_time_range"] = list(self.story_time_range)
        d["status"] = self.status
        return d


@dataclass
class ProjectConfig:
    series_name: str
    genre: str = "general"
    period: dict[str, Any] = field(default_factory=dict)
    llm: dict[str, Any] = field(default_factory=dict)
    books: list[BookEntry] = field(default_factory=list)
    defaults: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "series_name": self.series_name,
            "genre": self.genre,
            "period": dict(self.period),
            "llm": dict(self.llm),
            "books": [b.to_dict() for b in self.books],
            "defaults": dict(self.defaults),
        }

    def book_by_name(self, name: str) -> BookEntry | None:
        for b in self.books:
            if b.name == name:
                return b
        return None

    @classmethod
    def default(cls, series_name: str, genre: str = "general") -> "ProjectConfig":
        return cls(
            series_name=series_name,
            genre=genre,
            period={},
            llm={
                "heavy": "claude-opus-4-7",
                "standard": "claude-sonnet-4-6",
                "light": "claude-haiku-4-5-20251001",
                "thinking": {"heavy": True, "standard": False},
            },
            books=[],
            defaults={
                "chapter_target_words": 3200,
                "foundation_threshold": 7.5,
                "chapter_threshold": 6.0,
            },
        )


REQUIRED_FIELDS = ("series_name",)
LLM_REQUIRED = ("heavy", "standard", "light")


class ProjectValidationError(ValueError):
    pass


def load(path: Path) -> ProjectConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ProjectValidationError(f"{path}: project.yaml must be a mapping")
    return _from_dict(raw)


def dump(cfg: ProjectConfig, path: Path) -> None:
    path.write_text(
        yaml.safe_dump(cfg.to_dict(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _from_dict(raw: dict[str, Any]) -> ProjectConfig:
    for field_name in REQUIRED_FIELDS:
        if field_name not in raw:
            raise ProjectValidationError(f"project.yaml missing required field: {field_name}")

    books_raw = raw.get("books") or []
    if not isinstance(books_raw, list):
        raise ProjectValidationError("project.yaml: `books` must be a list")
    books: list[BookEntry] = []
    for i, b in enumerate(books_raw):
        if not isinstance(b, dict):
            raise ProjectValidationError(f"project.yaml: books[{i}] must be a mapping")
        if "name" not in b:
            raise ProjectValidationError(f"project.yaml: books[{i}] missing `name`")
        books.append(
            BookEntry(
                name=b["name"],
                pov=b.get("pov"),
                story_time_range=b.get("story_time_range"),
                status=b.get("status", "seed"),
            )
        )

    llm = raw.get("llm") or {}
    if llm and not isinstance(llm, dict):
        raise ProjectValidationError("project.yaml: `llm` must be a mapping")

    return ProjectConfig(
        series_name=raw["series_name"],
        genre=raw.get("genre", "general"),
        period=raw.get("period") or {},
        llm=llm,
        books=books,
        defaults=raw.get("defaults") or {},
    )


def validate(cfg: ProjectConfig) -> list[str]:
    """Return a list of validation problems (empty list == valid)."""
    problems: list[str] = []
    if not cfg.series_name or not isinstance(cfg.series_name, str):
        problems.append("series_name must be a non-empty string")
    if cfg.llm:
        for k in LLM_REQUIRED:
            if k not in cfg.llm:
                problems.append(f"llm.{k} missing")
    seen: set[str] = set()
    for b in cfg.books:
        if b.name in seen:
            problems.append(f"book name `{b.name}` appears more than once")
        seen.add(b.name)
        if b.story_time_range is not None:
            if (
                not isinstance(b.story_time_range, list)
                or len(b.story_time_range) != 2
                or not all(isinstance(x, int) for x in b.story_time_range)
                or b.story_time_range[0] > b.story_time_range[1]
            ):
                problems.append(
                    f"book `{b.name}` story_time_range must be [start, end] with start<=end"
                )
    return problems
