from __future__ import annotations

import datetime as dt
import os
import re
import string
import typing
from contextlib import contextmanager

from ..models import Movie

if typing.TYPE_CHECKING:
    from typing import List, Match, Optional, Pattern, Iterator, TextIO


__all__ = ["collect_local_info", "MovieDirNameParseError"]
MOVIE_DIR_REGEX: Pattern = re.compile(
    r"^(?P<title>.*)\s+\((?P<start_year>\d{4})\)(\s+\[(?P<quality>\d{3,}p)\])?"
)


class MovieDirNameParseError(ValueError):
    pass


def collect_local_info(movie_dir_path: str) -> Movie:
    """
    Collects all local info about give movie, without consulting IMDN
    """
    movie = _parse_dir_name(os.path.basename(movie_dir_path))
    return movie.replace(
        first_watch_time=_determine_first_watch_time(movie_dir_path),
        subtitles_languages=_determine_subtitles_languages(movie_dir_path),
        path=movie_dir_path,
    )


def _find_by_extensions(movie_dir_path: str, *extensions: str) -> List[str]:
    paths = (os.path.join(movie_dir_path, f) for f in os.listdir(movie_dir_path))
    return sorted(
        {f for f in paths for ext in extensions if os.path.splitext(f)[1] == f".{ext}"}
    )


def _determine_subtitles_languages(movie_dir_path: str) -> List[str]:
    res = set()
    for path in _find_by_extensions(movie_dir_path, "srt"):
        with _open_in_correct_encoding(path) as f:
            sample = set(f.read(8192))
        if sample.intersection("אבגדהוזחטיכךלמםנןסעפףצץקרשת"):
            res.add("Hebrew")
        elif sample.intersection(string.ascii_letters):
            res.add("English")
    return sorted(res)


@contextmanager
def _open_in_correct_encoding(
    path: str, encodings=("cp1255", "cp1256", "utf-8")
) -> Iterator[TextIO]:
    for i, encoding in enumerate(encodings, 1):
        with open(path, "r", encoding=encoding) as f:
            try:
                f.read(8192)
            except UnicodeDecodeError:
                if i == len(encodings):
                    raise
            else:
                f.seek(0)
                yield f
                break


def _determine_first_watch_time(movie_dir_path: str) -> Optional[dt.datetime]:
    times = [
        os.path.getatime(f)
        for f in _find_by_extensions(movie_dir_path, "mkv", "mp4", "avi")
    ]
    return dt.datetime.fromtimestamp(min(times)) if times else None


def _parse_dir_name(movie_dir_name: str) -> Movie:
    match: Optional[Match] = MOVIE_DIR_REGEX.match(movie_dir_name)
    if match is None:
        raise MovieDirNameParseError(f"Could not parse {movie_dir_name!r}")
    info: dict = match.groupdict()
    return Movie(
        title=info["title"],
        start_year=int(info["start_year"]),
        quality=info["quality"] or "720p",
    )
