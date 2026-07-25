from __future__ import annotations

from dataclasses import dataclass


@dataclass
class UnavailableVideo:
    """A playlist entry yt-dlp couldn't retrieve (private, deleted, region-locked, etc).

    Args:
        id (str | None): the video's id, if yt-dlp was able to report one.
        title (str | None): the video's title, if yt-dlp was able to report one.
        reason (str): a short human-readable reason it was skipped.
    """

    reason: str
    id: str | None = None
    title: str | None = None
