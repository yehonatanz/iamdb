from __future__ import annotations

import datetime as dt
from dataclasses import asdict as dataclass_asdict
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Mapping, Optional


@dataclass(frozen=True)
class Movie:
    # From IMDB database
    title: str
    start_year: int
    id: str = ""
    type: str = field(default="movie", repr=False)
    original_title: str = field(default="", repr=False)
    is_adult: bool = field(default=False, repr=False)
    end_year: Optional[int] = field(default=None, repr=False)
    minutes: Optional[int] = field(default=None, repr=False)
    genres: List[str] = field(default_factory=list)

    # Local data
    path: Optional[str] = field(default=None, repr=False)
    quality: Optional[str] = field(default=None, repr=False)
    first_watch_time: Optional[dt.datetime] = field(default=None, repr=False)
    subtitles_languages: List[str] = field(default_factory=list, repr=False)

    def asdict(self) -> Dict[str, Any]:
        return dict(dataclass_asdict(self), normalized_title=self.normalized_title)

    replace = replace

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> Movie:
        d = dict(d)
        d.pop("normalized_title", None)
        d["genres"] = (
            d["genres"].strip().split(",")
            if isinstance(d["genres"], str)
            else (d["genres"] or [])
        )
        d["is_adult"] = bool(int(d["is_adult"]))
        return cls(**d)

    def merge(self, movie: Movie) -> Movie:
        return self.from_dict(
            dict(
                self.asdict(),
                **{key: value for key, value in movie.asdict().items() if value},
            )
        )

    @property
    def normalized_title(self) -> str:
        return normalize_title(self.title)

    def __str__(self) -> str:
        quality = f" [{self.quality}]" if self.quality else ""
        return f"{self.title} ({self.start_year}){quality}"


def normalize_title(title: str) -> str:
    replacements = {
        "\\": " ",
        "/": " ",
        ":": " ",
        "*": " ",
        "?": " ",
        '"': " ",
        "<": " ",
        ">": " ",
        ",": " ",
        "|": " ",
        "-": " ",
        "'": "",
        "·": " ",
    }
    for src, dst in replacements.items():
        title = title.replace(src, dst)
    return " ".join(title.lower().split()).strip()
