from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spots_cli.models import Metadata, UnavailableVideo, YTVideoInfo


@dataclass
class PlaylistInfo:
    """
    A playlist metadata object.

    Args:
        cover (str): The playlist cover image.
        name (str): The playlist's name.
        artist (str, Optional): The artist of the playlist (if album). Defaults to None.
        provider_metadata (list[Metadata]): A list of provider metadata for the playlist.
        youtube_metadata (list[YTVideoInfo]): A list youtube metadata for the playlist.
        unavailable (list[UnavailableVideo], optional): Playlist entries yt-dlp
            failed to retrieve (private, deleted, region-locked, etc). Defaults to [].
    """

    name: str
    cover: str
    provider_metadata: list[Metadata]
    youtube_metadata: list[YTVideoInfo]
    artist: str | None = None
    unavailable: list[UnavailableVideo] = field(default_factory=list)
