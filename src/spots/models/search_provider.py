from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spots.bootstrap.container import Clients
    from spots.models import Metadata, PlaylistInfo, MetadataProvider


@dataclass
class ArtistInfo:
    name: str
    cover: str
    id: str


class SearchProvider(ABC):
    """Responsible for searching for query on a Media Provider"""

    @abstractmethod
    def __init__(
        self,
        *,
        metadata: MetadataProvider,
        clients: Clients,
        fallback_providers: list[SearchProvider] = [],
    ):
        self.fallback_providers = fallback_providers
        self.clients = clients
        self.metadata = metadata


    @abstractmethod
    def search_artist(self, artist_query: str) -> ArtistInfo:
        pass

    @abstractmethod
    def search_artist_top_tracks(self, *, artist_id: str) -> PlaylistInfo:
        pass

    @abstractmethod
    def search_playlist(self, playlist_url: str) -> PlaylistInfo:
        pass

    @abstractmethod
    def search_album(self, album_url: str) -> PlaylistInfo:
        pass

    @abstractmethod
    def search_track(self, query: str) -> Metadata:
        """Searches for a title on media provider

        Args:
            query (str): the title to be searched for

        Raises:
            SongNotFound: the `query` is not found.
            TypeError: if query format not: `Artist - Title`

        Returns:
            Metadata: The metadata of the title.
        """
        pass

