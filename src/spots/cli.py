from os.path import exists
from logging import getLogger
from typing import Callable
import typer

from spots import setup_env, Spots
from spots.utils import get_config_path
from spots.scripts import update_history, remove_duplicate_songs


logger = getLogger(__name__)

def ensure_config_exists():
    if not exists(get_config_path()):
        logger.info("Setup not run yet, running now...")
        setup_env.main()


app = typer.Typer()

@app.command()
def setup():
    setup_env.main()

@app.command()
def download(query: str):
    ensure_config_exists()

    app = Spots()
    app.download(query)

@app.command()
def migrate_likes():
    ensure_config_exists()

    app = Spots()
    app.transfer_spotify_likes()

@app.command()
def add_to_history(path_to_music: str):
    ensure_config_exists()

    add_to_history(path_to_music)

@app.command()
def remove_duplicates(path_to_music: str):
    ensure_config_exists()

    remove_duplicate_songs(path_to_music)

def main():
    app()
