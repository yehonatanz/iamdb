from __future__ import annotations

import functools
import os
from contextlib import contextmanager
from typing import Iterator, List, Optional

import click
import click_config_file
import pymongo

from . import config, localdb, passwd, remote, watched


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
        help="Write the current CLI params to the config file, making them the new defaults",
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
        cmd_name=config.CONFIG_DIR,
        config_file_name=config.CONFIG_NAME,
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
        if not (show_config or dry_write_config or write_config):
            return func(ctx, *args, **kwargs)

        _handle_config_options(
            ctx,
            show_config=show_config,
            dry_write_config=dry_write_config,
            write_config=write_config,
        )

    return wrapper


def _handle_config_options(
    ctx: click.Context, show_config: bool, dry_write_config: bool, write_config: bool
):
    if sum([show_config, dry_write_config, write_config]) > 1:
        raise click.UsageError(
            "Can specify only one of --write-config/--dry-write-config/--show-config"
        )
    # Get config value from params
    data_to_be_written = dict(ctx.params)
    data_to_be_written.pop("write_config")
    data_to_be_written.pop("show_config")
    data_to_be_written.pop("dry_write_config")

    config_path = ctx.obj["config_path"]
    key = ctx.info_name
    assert key
    if show_config:
        click.echo(f"Read from {config_path}:")
        click.echo(config.dumps(config.load(key, config_path=config_path)))
    elif dry_write_config:
        click.echo(f"Would write to {config_path} (key={key}):")
        click.echo(config.dumps(data_to_be_written))
    elif write_config:
        click.echo(f"Write to {config_path} (key={key})")
        config.set(key, data_to_be_written, config_path=config_path)


def json_provider(file_path: str, cmd_name: str) -> config.Config:
    config.initialize(file_path)
    return config.load(click.get_current_context().info_name, file_path)


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
    help="Opens a google search for an IMDB movie can't be resolved, only in interactive mode",
)
@click.option("-v", "--verbose", is_flag=True, help="Prints every checked movie")
@click.pass_context
@click_ipdb
@click_config
def check(ctx: click.Context, interactive: bool, auto_open_web: bool, verbose: bool):
    """
    Check that all watched movies can resolve IMDB data
    """
    with localdb.connect(ctx.obj["dbpath"]) as conn:
        for movie in watched.list_movies_dirs(
            ctx.obj["movies_dirs"],
            interactive=interactive,
            conn=conn,
            auto_open_web=auto_open_web,
        ):
            if verbose:
                click.echo(movie)


@cli.group("remote", invoke_without_command=True)
@click.option("-s", "--server", default="localhost", help="The remote mongodb server")
@click.option("-d", "--database", default="iamdb", help="mongodb database")
@click.option("-u", "--user", default="iamdb", help="mongodb username")
@click.option(
    "-p",
    "--force-password-prompt",
    is_flag=True,
    help="Force prompting for password instead of taking it from keyring",
)
@click.option(
    "-P", "--no-password-prompt", is_flag=True, help="Forbids prompting for password"
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
    database: str,
    user: str,
    no_auth: bool,
    force_password_prompt: bool,
    no_password_prompt: bool,
):
    """
    Sub-commands that handles all remote mongodb operations
    """
    password: Optional[str] = None
    if not no_auth:
        password = passwd.resolve_password(
            user,
            force_password_prompt=force_password_prompt,
            no_password_prompt=no_password_prompt,
        )
    uri = remote.format_uri(
        server=server, database=database, user=user, password=password, no_auth=no_auth
    )
    # Just check we are actually authenticated:
    if password and remote.connect(uri)[database].list_collection_names():
        passwd.save(user, password)
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
    Sync watched movies data to remote mongodb
    """
    with localdb.connect(ctx.obj["dbpath"]) as conn, _get_remote_database(
        ctx
    ) as remote_db:
        movies = list(watched.list_movies_dirs(ctx.obj["movies_dirs"], conn=conn))
        if verbose:
            click.echo(f"Syncing all {len(movies)} watched movies")
        response = remote.sync(remote_db, movies, replace_existing=True, watched=True)
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
        movies = list(localdb.sample(number, conn=conn))
        if verbose:
            click.echo(f"Syncing {number} random movies")
        # Don't wanna override watched information
        response = remote.sync(remote_db, movies, replace_existing=False, watched=True)
        _report_bulk_write(response, verbose=verbose)


if __name__ == "__main__":
    cli()
