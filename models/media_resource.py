from __future__ import annotations

from models.yt_video_info import YTVideoInfo
from models.metadata import Metadata
from dataclasses import dataclass
from typing import Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from models.playlist_info import PlaylistInfo


@dataclass
class MediaResourceSingle:
    resource_type: Literal["single"]
    metadata: Metadata | None
    video_info: YTVideoInfo | None

@dataclass
class MediaResourcePlaylist:
    resource_type: Literal["playlist"]
    playlist_info: PlaylistInfo

