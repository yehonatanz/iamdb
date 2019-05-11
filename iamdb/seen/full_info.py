from __future__ import annotations

import os
import sqlite3
import urllib.parse
from typing import Iterable, Optional

from ..localdb import MovieLookupError, fuzzy_find_in_db, get_by_id, optional_connect
from ..models import Movie
from . import cache
from .local_info import collect_local_info


def _list_movies_dirs(movies_dir: str) -> Iterable[str]:
    paths = (os.path.join(movies_dir, d) for d in os.listdir(movies_dir))
    return filter(os.path.isdir, paths)


def list_movies_local_info(movies_dir: str) -> Iterable[Movie]:
    return map(collect_local_info, _list_movies_dirs(movies_dir))


def list_movies_dirs(movies_dirs: Iterable[str], **kwargs) -> Iterable[Movie]:
    for movies_dir in movies_dirs:
        for movie in list_movies_full_info(movies_dir, **kwargs):
            yield movie


def list_movies_full_info(
    movies_dir: str,
    *,
    interactive: bool = False,
    conn: Optional[sqlite3.Connection] = None,
    auto_open_web: bool = False,
) -> Iterable[Movie]:
    with optional_connect(conn) as conn:
        for movie in list_movies_local_info(movies_dir):
            imdb_movie = _find_imdb_movie(
                movie, interactive=interactive, conn=conn, auto_open_web=auto_open_web
            )
            assert movie.path
            cache.cache_imdb_id(imdb_movie.id, movie.path)
            yield movie.merge(imdb_movie)


def _find_imdb_movie(
    movie: Movie,
    *,
    interactive: bool = False,
    conn: Optional[sqlite3.Connection] = None,
    auto_open_web: bool = False,
) -> Movie:
    """
    Tries its best to find an imdb match.
    Trying cache, fuzzy searching and user input, raises exception on failure.
    """
    try:
        assert movie.path
        return get_by_id(cache.load_imdb_id(movie.path))
    except FileNotFoundError:
        try:
            return fuzzy_find_in_db(
                title=movie.title, start_year=movie.start_year, conn=conn
            )
        except MovieLookupError:
            imdb_movie = interactive and _ask_user_for_imdb_id(
                movie, auto_open_web=auto_open_web
            )
            if imdb_movie:
                return imdb_movie
            else:
                raise


def _ask_user_for_imdb_id(movie: Movie, auto_open_web: bool = False) -> Optional[Movie]:
    import click

    url = _suggest_google_search(movie)
    if auto_open_web:
        import webbrowser

        webbrowser.open_new_tab(url)
    imdb_id = click.prompt(
        f'Please enter the IMDB id for {movie} (try looking in "{url}")'
    )
    movie = get_by_id(imdb_id)
    if click.confirm(f"Got {movie!r}. Correct?", default=True):
        return movie
    else:
        return None


def _suggest_google_search(movie: Movie) -> str:
    query = urllib.parse.quote_plus(
        f"{movie.title} {movie.start_year} site:www.imdb.com"
    )
    return f"https://www.google.com/search?q={query}"
