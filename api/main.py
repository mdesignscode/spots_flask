#!/usr/bin/python3
"""Spots Web App"""

from spots_cli.engine import storage
from logging import getLogger
from os import getenv
from requests import get
from server import app
from spots_cli.clients import SpotifyClient

# -----------------------------
# logging setup
# -----------------------------

logger = getLogger(__name__)


if __name__ == "__main__":
    # check network status
    try:
        get("https://www.google.com", timeout=10)
    except:
        logger.error("Network error. Check your internet connection.")
        quit()

    # sign user in
    spotify_client = SpotifyClient()

    if getenv("username"):
        spotify_client.signin()

    storage.reload()

    port = getenv("flask_port", "5000")

    logger.debug(f"Serving Spots on port {port}")

    app.run(port=int(port), debug=False)
