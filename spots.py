#!/usr/bin/python3
"""Spots Web App"""

from os import chdir, getenv
from engine import storage
from requests import get
from server import app, chdir_to_music


if __name__ == "__main__":
    # check network status
    try:
        get("https://www.google.com", timeout=2)
    except:
        print("Network error. Check your internet connection.")
        quit()

    root_dir = chdir_to_music()
    storage.reload()
    chdir(root_dir)

    port = getenv("flask_port", "5000")

    print(f"Serving Spots on port {port}")

    app.run(port=int(port), debug=True)
