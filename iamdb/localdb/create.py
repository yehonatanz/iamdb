from __future__ import annotations

import gzip
import itertools
import os
import typing
import urllib.request

from ..models import normalize_title
from .api import optional_connect

if typing.TYPE_CHECKING:
    import sqlite3
    from typing import Optional, Iterable, List, TypeVar

    T = TypeVar("T")

IMDB_DATA_TSV_GZ_PATH: str = os.path.join(
    os.path.expandvars("$TEMP"), "titles.basic.tsv.gz"
)


def _chunked(iterable: Iterable[T], chunk_size: int) -> Iterable[List[T]]:
    iterator = iter(iterable)
    while True:
        chunk = list(itertools.islice(iterator, chunk_size))
        if chunk:
            yield chunk
        else:
            break


def _line_to_row(line: str) -> List[Optional[str]]:
    return [None if part == "\\N" else part for part in line.strip().split("\t")]


def create_sqlite_schema(conn: Optional[sqlite3.Connection] = None):
    with optional_connect(conn) as conn:
        conn.execute("DROP TABLE IF EXISTS movies")
        conn.execute(
            """
            CREATE TABLE movies(
                "id" TEXT PRIMARY KEY,
                "type" TEXT,
                "title" TEXT,
                "original_title" TEXT,
                "is_adult" BOOLEAN,
                "start_year" INT,
                "end_year" INT,
                "minutes" INT,
                "genres" TEXT,
                "normalized_title" TEXT
             );"""
        )


def finalize_schema(conn: Optional[sqlite3.Connection] = None):
    with optional_connect(conn) as conn:
        conn.executescript(
            """
            CREATE INDEX normalized_title_start_year ON movies(normalized_title, start_year);
            CREATE INDEX start_year ON movies(start_year);
        """
        )


COLUMNS_MAPPING = {
    "tconst": "id",
    "titleType": "type",
    "primaryTitle": "title",
    "originalTitle": "original_title",
    "isAdult": "is_adult",
    "startYear": "start_year",
    "endYear": "end_year",
    "runtimeMinutes": "minutes",
    "genres": "genres",
}


def tsv_gz_to_sqlite(
    tsv_gz_path: str = IMDB_DATA_TSV_GZ_PATH,
    conn: Optional[sqlite3.Connection] = None,
    chunk_size: int = 1 << 17,
):
    # read tab-delimited file
    with gzip.open(tsv_gz_path, mode="rt", encoding="utf-8") as fin, optional_connect(
        conn
    ) as conn:
        rows = map(_line_to_row, fin)
        headers = [COLUMNS_MAPPING[str(h)] for h in next(rows)]
        columns = (*headers, "normalized_title")
        cur = conn.cursor()
        for i, batch in enumerate(_chunked(rows, chunk_size), 1):
            print(f"Batch #{i}")
            normalized_batch = [(*row, normalize_title(str(row[2]))) for row in batch]
            print(
                cur.executemany(
                    "INSERT INTO movies({}) VALUES ({})".format(
                        ", ".join(columns), ", ".join("?" for c in columns)
                    ),
                    normalized_batch,
                ).fetchall()
            )
        conn.commit()


def download_tsv_gz(
    url: str = "https://datasets.imdbws.com/title.basics.tsv.gz",
    path: str = IMDB_DATA_TSV_GZ_PATH,
) -> str:
    return urllib.request.urlretrieve(url, filename=path)[0]
