from __future__ import annotations

from typing import TYPE_CHECKING

from spots.models import SongNotFound

if TYPE_CHECKING:
    from spots.models import Metadata, SearchProvider


def search_fallbacks(*, query: str, providers: list[SearchProvider]) -> Metadata:
    index = 0
    while index < len(providers):
        provider = providers[index]
        try:
            return provider.search_track(query)
        except SongNotFound:
            index += 1
            continue

    raise SongNotFound(query)

