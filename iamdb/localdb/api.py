from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from typing import Iterable, Iterator, Optional

from ..models import Movie, normalize_title

__all__ = [
    "IMDB_TITLES_SQLITE_PATH",
    "MovieLookupError",
    "MovieNotFound",
    "MultipleMoviesFound",
    "connect",
    "optional_connect",
    "fuzzy_find_in_db",
    "get_by_id",
    "sample",
]

IMDB_TITLES_SQLITE_PATH: str = os.path.join(os.path.expanduser("~"), "imadb.db")


class MovieLookupError(LookupError):
    pass


class MovieNotFound(MovieLookupError):
    pass


class MultipleMoviesFound(MovieLookupError):
    pass


def connect(*args, **kwargs) -> sqlite3.Connection:
    conn = sqlite3.connect(*args, **kwargs)
    conn.row_factory = lambda cursor, row: {
        col[0]: value for col, value in zip(cursor.description, row)
    }
    return conn


@contextmanager
def optional_connect(
    conn: Optional[sqlite3.Connection] = None
) -> Iterator[sqlite3.Connection]:
    """
    Wraps an optional connection in a context manager that closes the connection if it was None (does not close given existing connection).
    Useful for connection propagation.
    """
    temp_connect = False
    if not conn:
        temp_connect = True
        conn = connect(IMDB_TITLES_SQLITE_PATH)
    try:
        yield conn
    finally:
        if temp_connect:
            conn.close()


def fuzzy_find_in_db(
    title: str, start_year: int, conn: Optional[sqlite3.Connection] = None
) -> Movie:
    """
    Searches for a movie in the local IMDB clone.
    Prefers movies over non movies (tv episodes, video games, etc.).
    Raises exception when no definitive match is found (MovieLookupError).
    """
    with optional_connect(conn) as conn:
        cursor = conn.execute(
            "SELECT * FROM movies WHERE normalized_title = ? AND start_year = ?",
            [normalize_title(title), start_year],
        )
        matches = list(map(Movie.from_dict, cursor.fetchall()))

    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise MovieNotFound(f"Could not find matches for: {title} ({start_year})")

    movies = [m for m in matches if m.type == "movie"]
    if len(movies) == 1:
        # Prefer movie over other types (tv episodes, etc.)
        return movies[0]
    else:
        raise MultipleMoviesFound(
            f"{len(matches)} matches (and {len(movies)} movies) found for: {title} ({start_year})"
        )


def get_by_id(imdb_id: str, *, conn: Optional[sqlite3.Connection] = None) -> Movie:
    with optional_connect(conn) as conn:
        return Movie.from_dict(
            conn.execute("SELECT * FROM movies WHERE id = ?", [imdb_id]).fetchone()
        )


def sample(n: int, conn: Optional[sqlite3.Connection] = None) -> Iterable[Movie]:
    """
    Provies n random movies from the local IMDB clone
    """
    with optional_connect(conn) as conn:
        return map(
            Movie.from_dict,
            conn.execute(
                """
                    SELECT * FROM movies WHERE id IN (
                        SELECT id FROM movies ORDER BY RANDOM() LIMIT ?
                    )""",
                [n],
            ).fetchall(),
        )
