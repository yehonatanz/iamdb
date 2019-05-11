from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Iterable, Optional, Union
from urllib.parse import quote_plus

import pymongo

from . import config, passwd
from .models import Movie


def to_doc(movie: Movie) -> Dict[str, Any]:
    doc = movie.asdict()
    doc["_id"] = doc.pop("id")
    return doc


def connect(uri: Optional[str]) -> pymongo.MongoClient:
    return pymongo.MongoClient(uri or _format_uri_from_config())


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


def format_uri(
    server: str,
    *,
    password: Optional[str] = None,
    user: str = "iamdb",
    database: str = "iamdb",
    no_auth: bool = False,
    force_password_prompt: bool = False,
    no_password_prompt: bool = True,
) -> str:
    if no_auth:
        auth = ""
    else:
        resolved_password = passwd.resolve_password(
            user,
            password=password,
            force_password_prompt=force_password_prompt,
            no_password_prompt=no_password_prompt,
        )
        auth = f"{quote_plus(user)}:{quote_plus(resolved_password)}@"
    return f"mongodb+srv://{auth}{server}/{database}?retryWrites=true"


def _format_uri_from_config(data: Optional[config.Config] = None) -> str:
    data = data or config.load("remote")
    server: str = data["server"]
    user: str = data["user"]
    database: str = data["database"]
    no_auth: bool = data["no_auth"]
    force_password_prompt: bool = data["force_password_prompt"]
    no_password_prompt: bool = data["no_password_prompt"]
    return format_uri(
        server=server,
        user=user,
        database=database,
        no_auth=no_auth,
        force_password_prompt=force_password_prompt,
        no_password_prompt=no_password_prompt,
    )
