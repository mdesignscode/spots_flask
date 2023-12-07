#!/usr/bin/python3
"""Spots Web App"""

from engine import storage
from requests import get
from server import app


if __name__ == "__main__":
    # check network status
    try:
        get("https://www.google.com", timeout=2)
    except:
        print("Network error. Check your internet connection.")
        quit()

    storage.reload()

    app.run(debug=True)
