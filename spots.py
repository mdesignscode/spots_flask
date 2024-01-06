#!/usr/bin/python3
"""Spots Web App"""

from logging import ERROR, basicConfig, error, info
from os import chdir, getenv
from requests import get
from models import spotify_model
from server import app, chdir_to_music


if __name__ == "__main__":
    from engine import storage

    # check network status
    try:
        get("https://www.google.com", timeout=2)
    except:
        basicConfig(level=ERROR)
        error("Network error. Check your internet connection.")
        quit()

    # go to Music folder to reload storage objects
    root_dir = chdir_to_music()
    storage.reload()

    # sign user in
    spotify_model.signin()

    # change back to root path
    chdir(root_dir)

    port = getenv("flask_port", "5000")

    info(f"Serving Spots on port {port}")

    app.run(port=int(port))
