#!/usr/bin/python3
"""Spots Web App"""

from engine.persistence_model import storage
from logging import basicConfig, error, info, INFO
from os import getenv, makedirs
from requests import get
from server import app
from clients.spotify import SpotifyClient

basicConfig(level=INFO)


if __name__ == "__main__":
    # check network status
    try:
        get("https://www.google.com", timeout=10)
    except:
        error("Network error. Check your internet connection.")
        quit()

    # sign user in
    spotify_client = SpotifyClient()

    if getenv("username"):
        spotify_client.signin()

    makedirs("./Music", exist_ok=True)

    storage.reload()

    port = getenv("flask_port", "5000")

    info(f"Serving Spots on port {port}")

    app.run(port=int(port), debug=False)

