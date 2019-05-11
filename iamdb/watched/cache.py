import json
import os

CACHE_FILE_NAME = ".iamdb.json"


def get_cache_path(movie_dir_path: str) -> str:
    return os.path.join(movie_dir_path, CACHE_FILE_NAME)


def load(movie_dir_path: str):
    with open(get_cache_path(movie_dir_path), "r") as f:
        return json.load(f)


def _override(info: dict, movie_dir_path: str):
    with open(get_cache_path(movie_dir_path), "w") as f:
        json.dump(info, f)


def update(info: dict, movie_dir_path: str):
    try:
        cached = load(movie_dir_path)
    except FileNotFoundError:
        cached = dict()
    data = dict(cached, **info)
    _override(data, movie_dir_path)
    return data


def cache_imdb_id(imdb_id: str, movie_dir_path: str):
    update({"id": imdb_id}, movie_dir_path)


def load_imdb_id(movie_dir_path: str):
    return load(movie_dir_path)["id"]


def has(movie_dir_path: str) -> bool:
    return os.path.exists(get_cache_path(movie_dir_path))
