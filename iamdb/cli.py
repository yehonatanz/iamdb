from __future__ import annotations

import functools
import json
import os
from contextlib import contextmanager
from typing import Iterator, List
from urllib.parse import quote_plus

import click
import click_config_file
import keyring
import pymongo

from . import localdb, remote, seen


def click_ipdb(func):
    @functools.wraps(func)
    def wrapper(ctx: click.Context, *args, **kwargs):
        if ctx.obj["pdb"]:
            from ipdb import launch_ipdb_on_exception

            with launch_ipdb_on_exception():
                return func(ctx, *args, **kwargs)
        else:
            return func(ctx, *args, **kwargs)

    return wrapper


def click_config(func):
    @click.option(
        "--write-config",
        is_flag=True,
        help="Write the current CLI params to the config file, effectively making them the new default",
    )
    @click.option(
        "--dry-write-config",
        is_flag=True,
        help="Show what will be written to the config file, without actually writing",
    )
    @click.option(
        "--show-config", is_flag=True, help="Show the contents of the config file"
    )
    @click_config_file.configuration_option(
        cmd_name="iamdb",
        config_file_name="imdb.json",
        provider=json_provider,
        callback=configuration_callback,
    )
    @functools.wraps(func)
    def wrapper(
        ctx: click.Context,
        *args,
        write_config: bool,
        show_config: bool,
        dry_write_config: bool,
        **kwargs,
    ):
        ctx.obj = dict(ctx.obj or {}, params={})
        params = dict(ctx.params)
        params.pop("write_config")
        params.pop("show_config")
        params.pop("dry_write_config")
        key = ctx.info_name
        assert key
        ctx.obj["params"][key] = params

        if not (show_config or dry_write_config or write_config):
            return func(ctx, *args, **kwargs)
        if sum([show_config, dry_write_config, write_config]) > 1:
            raise click.UsageError(
                "Can specify only one of --write-config/--dry-write-config/--show-config"
            )

        config_path = ctx.obj["config_path"]
        with open(config_path, "r") as f:
            config = json.load(f)
        config_to_be_written = ctx.obj["params"][key]
        if show_config:
            click.echo(f"Read from {config_path}:")
            click.echo(json.dumps(config, indent=2))
        elif dry_write_config:
            click.echo(f"Would write to {config_path} (key={key}):")
            click.echo(json.dumps(config_to_be_written, indent=2))
        elif write_config:
            click.echo(f"Write to {config_path} (key={key})")
            with open(config_path, "w") as f:
                json.dump(dict(config, **{key: config_to_be_written}), f, indent=2)

    return wrapper


def json_provider(file_path: str, cmd_name: str) -> dict:
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    if not os.path.exists(file_path):
        with open(file_path, "w") as f:
            json.dump({}, f)
    with open(file_path, "r") as f:
        return json.load(f).get(click.get_current_context().info_name, {})


def configuration_callback(ctx: click.Context, _, config_path: str):
    ctx.obj = dict(ctx.obj or {}, config_path=config_path)


@click.group("iamdb", invoke_without_command=True)
@click.option(
    "--dbpath",
    default=localdb.IMDB_TITLES_SQLITE_PATH,
    help="Path to local sqlite cache of IMDB data",
)
@click.option(
    "-m",
    "--movies-dir",
    multiple=True,
    help="A directory to search for movies, may be specified multiple times",
    type=click.Path(dir_okay=True, file_okay=False, exists=True),
)
@click.option("--pdb", is_flag=True, help="Launch ipdb on exception")
@click.pass_context
@click_config
def cli(ctx: click.Context, dbpath: str, movies_dir: List[str], pdb: bool):
    if not movies_dir:
        click.echo("No movies directories were given, nothing to do")
        click.echo("Either specify via -m/--movies-dir or add some to config file")
        click.echo("iamdb -m /path/to/movies/dir --write-config")
        raise click.Abort()
    ctx.obj = dict(ctx.obj or {}, dbpath=dbpath, movies_dirs=movies_dir, pdb=pdb)


@cli.command("localdb")
@click.option(
    "--force-redownload",
    is_flag=True,
    help="Always download TSV from IMDB, implies rebuild",
)
@click.option(
    "--force-rebuild",
    is_flag=True,
    help="Rebuild the sqlite cache, even if the file already exists",
)
@click.option(
    "--tsv-gz-path",
    default=localdb.create.IMDB_DATA_TSV_GZ_PATH,
    help="Path to TSV, if not exists will trigger download and delete",
)
@click.pass_context
@click_ipdb
@click_config
def localdb_cli(
    ctx: click.Context, force_redownload: bool, force_rebuild: bool, tsv_gz_path: str
):
    """
    Generate the local sqlite from the public IMDB TSV
    """
    dbpath = ctx.obj["dbpath"]
    force_rebuild = force_rebuild or force_redownload
    if os.path.exists(dbpath) and not force_rebuild:
        click.confirm(f"DB already exists ({dbpath})! Overwrite?", abort=True)

    downloaded = False
    if force_redownload or not os.path.exists(tsv_gz_path):
        click.echo("Downloading tsv.gz... This might take a while")
        tsv_gz_path = localdb.create.download_tsv_gz(path=tsv_gz_path)
        downloaded = True

    with localdb.connect(dbpath) as conn:
        click.echo("Creating sqlite schema")
        localdb.create.create_sqlite_schema(conn=conn)
        click.echo("Importing tsv into sqlite... This might take a while")
        localdb.create.tsv_gz_to_sqlite(tsv_gz_path, conn=conn)
        if downloaded:
            click.echo("Removing tsv")
            os.remove(tsv_gz_path)
        click.echo("Finalizing schema... This might take a while")
        localdb.create.finalize_schema(conn=conn)
        click.echo("Done!")


@cli.command()
@click.option(
    "-i",
    "--interactive",
    is_flag=True,
    help="Prompts the user for help when IMDB movie cannot be resolved",
)
@click.option(
    "-o",
    "--auto-open-web",
    is_flag=True,
    help="Opens a google search for the user when cannot resolve IMDB movie, only in interactive",
)
@click.option("-v", "--verbose", is_flag=True, help="Prints every checked movie")
@click.pass_context
@click_ipdb
@click_config
def check(ctx: click.Context, interactive: bool, auto_open_web: bool, verbose: bool):
    """
    Check that all seen movies can resolve IMDB data
    """
    with localdb.connect(ctx.obj["dbpath"]) as conn:
        for movie in seen.list_movies_dirs(
            ctx.obj["movies_dirs"],
            interactive=interactive,
            conn=conn,
            auto_open_web=auto_open_web,
        ):
            if verbose:
                click.echo(movie)


@cli.group("remote", invoke_without_command=True)
@click.option("-s", "--server", default="localhost", help="The remote mongodb server")
@click.option("-u", "--user", default="iamdb", help="mongodb username")
@click.option("-d", "--database", default="iamdb", help="mongodb database")
@click.option(
    "-P",
    "--prompt-password",
    is_flag=True,
    help="Force prompting for password instead of taking it from keyring",
)
@click.option(
    "--no-auth",
    is_flag=True,
    help="Indicates no auth is required to connect to mongodb",
)
@click.pass_context
@click_ipdb
@click_config
def remote_cli(
    ctx: click.Context,
    server: str,
    user: str,
    no_auth: bool,
    database: str,
    prompt_password: bool,
):
    """
    Sub-commands that handles all remote mongodb operations
    """
    if no_auth:
        auth = ""
    else:
        password = ""
        if not prompt_password:
            password = keyring.get_password("iamdb", user)
        password = password or click.prompt(f"Password for {user}", hide_input=True)
        keyring.set_password("iamdb", user, password)
        auth = f"{quote_plus(user)}:{quote_plus(password)}@"
    uri = f"mongodb+srv://{auth}{server}/{database}?retryWrites=true"
    ctx.obj["mongodb_uri"] = uri
    ctx.obj["mongodb_database"] = database


@contextmanager
def _get_remote_database(ctx: click.Context) -> Iterator[pymongo.database.Database]:
    with remote.connect(ctx.obj["mongodb_uri"]) as client:
        yield client[ctx.obj["mongodb_database"]]


def _report_bulk_write(response: pymongo.results.BulkWriteResult, *, verbose: bool):
    if verbose:
        new = response.inserted_count + response.upserted_count
        if new:
            click.echo(f"{new} new movies")
        if response.modified_count:
            click.echo(f"{response.modified_count} movies updated")


@remote_cli.command()
@click.option("-v", "--verbose", is_flag=True)
@click.pass_context
@click_ipdb
@click_config
def sync(ctx, verbose: bool):
    """
    Sync seen movies data to remote mongodb
    """
    with localdb.connect(ctx.obj["dbpath"]) as conn, _get_remote_database(
        ctx
    ) as remote_db:
        movies = list(seen.list_movies_dirs(ctx.obj["movies_dirs"]))
        if verbose:
            click.echo(f"Syncing all {len(movies)} seen movies")
        response = remote.sync(remote_db, movies, replace_existing=True, seen=True)
        _report_bulk_write(response, verbose=verbose)


@remote_cli.command()
@click.option("-n", "--number", type=int, default=20000)
@click.option("-v", "--verbose", is_flag=True)
@click.pass_context
@click_ipdb
@click_config
def sample(ctx, number: int, verbose: bool):
    """
    Populates the remote DB with a random sample from local IMDB
    """
    with localdb.connect(ctx.obj["dbpath"]) as conn, _get_remote_database(
        ctx
    ) as remote_db:
        if verbose:
            click.echo(f"Sampling {number} rows")
        movies = list(localdb.sample(number))
        if verbose:
            click.echo(f"Syncing {number} random movies")
        # Don't wanna override seen information
        response = remote.sync(remote_db, movies, replace_existing=False, seen=True)
        _report_bulk_write(response, verbose=verbose)


if __name__ == "__main__":
    cli()
