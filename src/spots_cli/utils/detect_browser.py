from __future__ import annotations

import shutil
from typing import Optional, Tuple


def detect_browser() -> Optional[Tuple[str, ...]]:
    """
    Detect an installed browser and return a yt-dlp compatible
    cookiesfrombrowser tuple.

    Returns:
        Tuple usable in yt-dlp options, e.g. ("firefox",)
        or ("chrome",), or None if nothing found.
    """

    # Order matters: prefer Firefox (more reliable on Linux)
    browsers = [
        ("firefox", ["firefox"]),
        ("chrome", ["google-chrome", "chrome", "chromium", "chromium-browser"]),
        ("edge", ["microsoft-edge"]),
        ("brave", ["brave-browser"]),
    ]

    for browser_name, executables in browsers:
        for exe in executables:
            if shutil.which(exe):
                return (browser_name,)

    return None
