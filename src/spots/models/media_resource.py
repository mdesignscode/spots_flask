from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from spots.models import PlaylistInfo, YTVideoInfo, Metadata


@dataclass
class MediaResourceSingle:
    resource_type: Literal["single"]
    metadata: Metadata | None
    video_info: YTVideoInfo | None

@dataclass
class MediaResourcePlaylist:
    resource_type: Literal["playlist"]
    playlist_info: PlaylistInfo

