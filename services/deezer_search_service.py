from __future__ import annotations

from typing import Any, TypedDict, cast, TYPE_CHECKING

from models import (
    Metadata,
    SearchProvider,
    PlaylistInfo,
    ArtistInfo,
    MetadataProvider,
    SongNotFound,
)
from services.providers_search import ProvidersSearch

if TYPE_CHECKING:
    from bootstrap.container import Clients
    from services import ProvidersSearch


class DeezerResponseBase(TypedDict):
    total: int
    data: list[dict[str, Any]]


class DeezerSearchService(SearchProvider):
    def __init__(
        self,
        *,
        metadata: MetadataProvider,
        clients: Clients,
        providers: ProvidersSearch,
    ):
        self.clients = clients
        self.metadata = metadata
        self.providers = providers

    def search_album(self, album_url: str) -> PlaylistInfo:
        album_data = self.clients.deezer._get_resource_by_url(album_url)

        album_metadata = [
            self.metadata.get(search_result=result) for result in album_data["tracks"]
        ]
        artist_name = album_data["artist"]["name"]
        return PlaylistInfo(
            name=album_data["title"],
            cover=album_data["cover"],
            provider_metadata=album_metadata,
            youtube_metadata=[],
            artist=artist_name,
        )

    def search_playlist(self, playlist_url: str) -> PlaylistInfo:
        playlist_data = self.clients.deezer._get_resource_by_url(playlist_url)

        playlist_metadata = [
            self.metadata.get(search_result=result)
            for result in playlist_data["tracks"]
        ]
        return PlaylistInfo(
            name=playlist_data["title"],
            cover=playlist_data["picture"],
            provider_metadata=playlist_metadata,
            youtube_metadata=[],
        )

    def search_artist(self, artist_query: str) -> ArtistInfo:
        # deezer provides a list of search results
        # so we use the first result
        metadata = self.search_track(artist_query)

        cover = cast(str, metadata.artist_cover)
        return ArtistInfo(name=metadata.artist, cover=cover, id=metadata.artist_id)

    def search_artist_top_tracks(self, *, artist_id: str) -> PlaylistInfo:
        try:
            artist_id_int = int(artist_id)
        except ValueError:
            raise TypeError("Number ids required")

        artist_info, top_tracks = self.clients.deezer.artist_top_tracks(artist_id_int)

        # get metadata for each top track
        top_tracks_playlist = [
            self.metadata.get(track_id=top_track["id"]) for top_track in top_tracks
        ]

        return PlaylistInfo(
            cover=artist_info.cover,
            name="Top Tracks",
            artist=artist_info.name,
            provider_metadata=top_tracks_playlist,
            youtube_metadata=[],
        )

    def search_track(self, query: str) -> Metadata:
        try:
            track_id = self.clients.deezer.search(query)
            return self.metadata.get(track_id=track_id)
        except SongNotFound:
            return self.providers.fallback(query)

