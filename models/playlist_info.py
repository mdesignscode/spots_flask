from dataclasses import dataclass
from models.metadata import Metadata
from models.yt_video_info import YTVideoInfo


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
    """

    name: str
    cover: str
    provider_metadata: list[Metadata]
    youtube_metadata: list[YTVideoInfo]
    artist: str | None = None

