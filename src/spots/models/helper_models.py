from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spots.models import YTVideoInfo


@dataclass
class ArtistAndTitle:
    title: str
    artist: str

@dataclass
class SearchResponseSingle():
    result: YTVideoInfo
    is_cached: bool


@dataclass
class SearchResponseMultiple():
    result: list[YTVideoInfo]
    is_cached: bool

