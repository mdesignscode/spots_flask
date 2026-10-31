from __future__ import annotations

import shutil
from pathlib import Path
from typing import Dict


def detect_js_runtimes() -> Dict[str, dict]:
    """
    Detect JavaScript runtimes yt-dlp can use to solve YouTube's JS challenges.

    Without a supported runtime, yt-dlp extracts stream URLs it cannot
    authorise, and YouTube cuts the download off part-way with a 403.

    Every runtime found is listed; yt-dlp skips any it considers unsupported
    (e.g. Node older than its minimum) and uses the first one that works.

    Returns:
        A yt-dlp `js_runtimes` option, e.g. {"bun": {"path": "..."}, "node": {}}.
    """
    # common install locations that may not be on PATH for a GUI- or service-launched process
    fallback_paths = {
        "deno": Path.home() / ".deno" / "bin" / "deno",
        "bun": Path.home() / ".bun" / "bin" / "bun",
    }

    runtimes: Dict[str, dict] = {}
    for name in ("deno", "bun", "node", "quickjs"):
        exe = shutil.which(name)
        if not exe and name in fallback_paths and fallback_paths[name].exists():
            exe = str(fallback_paths[name])
        if exe:
            runtimes[name] = {"path": exe}

    return runtimes
