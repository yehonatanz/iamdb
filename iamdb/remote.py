from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Iterable, Optional, Union

import pymongo

from .models import Movie


def to_doc(movie: Movie) -> Dict[str, Any]:
    doc = movie.asdict()
    doc["_id"] = doc.pop("id")
    return doc


def connect(uri: str) -> pymongo.MongoClient:
    return pymongo.MongoClient(uri)


def sync(
    db: pymongo.database.Database,
    movies: Iterable[Movie],
    *,
    replace_existing: bool = False,
    **extras,
) -> pymongo.results.BulkWriteResult:

    ops = list(map(_movie_to_operation, movies))
    return db.movies.bulk_write(ops, ordered=False)


def _movie_to_operation(
    movie: Movie, replace_existing: bool = False, **extras
) -> Union[pymongo.ReplaceOne, pymongo.UpdateOne]:
    match = {"_id": movie.id}
    doc = dict(to_doc(movie), **extras)
    if replace_existing:
        return pymongo.ReplaceOne(match, doc, upsert=True)
    else:
        return pymongo.UpdateOne(match, {"$setOnInsert": doc}, upsert=True)
