#!/usr/bin/python3
"""Spots Web App"""

from logging import getLogger
from os import getenv
from requests import get
from requests.exceptions import ConnectionError

from server import app


logger = getLogger(__name__)

if __name__ == "__main__":
    # check network status
    try:
        get("https://www.google.com", timeout=10)
    except ConnectionError:
        logger.error("Network error. Check your internet connection.")
        quit()

    port = getenv("flask_port", "5000")

    logger.debug(f"Serving Spots on port {port}")

    app.run(port=int(port), debug=True)
