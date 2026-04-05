from os.path import exists
from logging import getLogger
from typing import Callable
import typer

from spots_cli import setup_env, Spots
from spots_cli.scripts import remove_duplicate_songs, update_history

logger = getLogger(__name__)

app = typer.Typer()


@app.command()
def setup():
    setup_env.main()


@app.command()
def download(query: str):
    app = Spots()
    app.download(query)


@app.command()
def migrate_likes():
    app = Spots()
    app.transfer_spotify_likes()


@app.command()
def add_to_history(path_to_music: str):
    update_history(path_to_music)


@app.command()
def remove_duplicates(path_to_music: str):
    remove_duplicate_songs(path_to_music)


def main():
    app()
