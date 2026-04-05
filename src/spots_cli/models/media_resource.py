from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from spots_cli.models import PlaylistInfo, YTVideoInfo, Metadata


@dataclass
class MediaResourceSingle:
    resource_type: Literal["single"]
    metadata: Metadata
    video_info: YTVideoInfo


@dataclass
class MediaResourcePlaylist:
    resource_type: Literal["playlist"]
    playlist_info: PlaylistInfo
