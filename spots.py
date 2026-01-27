#!/usr/bin/python3
"""Spots Web App"""

from logging import basicConfig, error, info, INFO
from os import getenv, makedirs
from requests import get
from server import app

basicConfig(level=INFO)


if __name__ == "__main__":
    # check network status
    try:
        get("https://www.google.com", timeout=10)
    except:
        error("Network error. Check your internet connection.")
        quit()

    # sign user in
    from models import spotify_client

    if getenv("username"):
        spotify_client.signin()

    makedirs("./Music", exist_ok=True)

    from engine import storage
    storage.reload()
    print(f"Songs liked on YT already: {len(storage.all()['yt_likes'])}")

    port = getenv("flask_port", "5000")

    info(f"Serving Spots on port {port}")

    app.run(port=int(port), debug=False)

