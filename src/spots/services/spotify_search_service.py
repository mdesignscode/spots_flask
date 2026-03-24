from __future__ import annotations
from logging import info, error
from re import escape, search
from tenacity import stop_after_delay
from typing import Any, TYPE_CHECKING

from engine.persistence_model import storage
from engine.retry import retry
from models import (
    SongNotFound,
    Metadata,
    PlaylistInfo,
    SearchProvider,
    Sentinel,
    ArtistInfo,
)
from utils import search_fallbacks

if TYPE_CHECKING:
    from bootstrap.container import Clients
    from models import MetadataProvider


class SpotifySearchService(SearchProvider):
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

    def search_artist(self, artist_query: str) -> ArtistInfo:
        artist_url = "https://open.spotify.com/artist/"
        artist_id = ""

        # get artist by id
        if artist_url in artist_query:
            artist_id = artist_query.replace(artist_url, "").split("?")[0]
            result = self.clients.spotify.client.artist(artist_id)

            if not result:
                raise SongNotFound(artist_query)

        else:
            # search for the artist
            result = self.clients.spotify.client.search(artist_query, 1, type="artist")

            if not result:
                raise SongNotFound(artist_query)

            result = result["artists"]["items"][0]

        return result

    def search_artist_top_tracks(self, *, artist_id: str) -> PlaylistInfo:
        artist_details = self.clients.spotify.client.artist(artist_id)
        if not artist_details:
            raise SongNotFound(artist_id)

        artist_name = artist_details["name"]
        artist_cover = artist_details["images"][0]["url"]

        top_tracks_search = self.clients.spotify.client.artist_top_tracks(artist_id)
        if not top_tracks_search:
            raise SongNotFound(artist_id)

        # get metadata for each top track
        top_tracks_playlist = [
            self.metadata.get(track_id=top_track["id"])
            for top_track in top_tracks_search["tracks"]
        ]

        return PlaylistInfo(
            cover=artist_cover,
            name="Top Tracks",
            artist=artist_name,
            provider_metadata=top_tracks_playlist,
            youtube_metadata=[],
        )

    def search_playlist(self, playlist_url: str) -> PlaylistInfo:
        playlist_result = self.clients.spotify.client.playlist(playlist_url)

        if not playlist_result:
            raise SongNotFound(playlist_url)

        # get playlist tracks
        playlist_tracks: list[dict[str, Any]] = playlist_result["tracks"]["items"]

        playlist_metadata = [
            self.metadata.get(search_result=track) for track in playlist_tracks
        ]

        cover = playlist_result["images"][0]["url"]
        playlist_name = playlist_result["name"]
        artist = None

        return PlaylistInfo(
            cover=cover,
            artist=artist,
            name=playlist_name,
            provider_metadata=playlist_metadata,
            youtube_metadata=[],
        )

    def search_album(self, album_url: str) -> PlaylistInfo:
        album_result = self.clients.spotify.client.album(album_url)
        if not album_result:
            raise SongNotFound(album_url)

        # artists
        artist_list = [artist["name"] for artist in album_result["artists"]]

        # get album tracks
        playlist_tracks: list[dict[str, Any]] = album_result["tracks"]["items"]

        playlist_metadata = [
            self.metadata.get(search_result=track) for track in playlist_tracks
        ]

        cover = album_result["images"][0]["url"]
        album_name = album_result["name"]
        artist = ", ".join(artist_list)

        return PlaylistInfo(
            cover=cover,
            artist=artist,
            name=album_name,
            provider_metadata=playlist_metadata,
            youtube_metadata=[],
        )

    @retry(stop=stop_after_delay(60))
    def search_track(self, query: str) -> Metadata:
        """Searches for a title on spotify

        Args:
            query (str): the title to be searched for

        Raises:
            SongNotFound: the `query` is not found on spotify.
            TypeError: if query format not: `Artist - Title`

        Returns:
            Metadata: The metadata of the title.
        """
        query = query.replace("–", "-")  # `–` != `-`

        if "-" not in query:
            error_txt = "Search format: `Artist` - `Title`"
            error(error_txt)
            raise TypeError(error_txt)

        cache = storage.get(query=query, query_type="metadata")
        if isinstance(cache, Sentinel):
            raise SongNotFound(query)
        elif isinstance(cache, Metadata):
            return cache

        # search for a single
        single_result = self.clients.spotify.client.search(query)

        if not single_result:
            info(f"{query} not found")
            return search_fallbacks(query=query, providers=self.fallback_providers)

        try:
            track_id = single_result["tracks"]["items"][0]["id"]
        except IndexError:
            raise SongNotFound(query)

        single_data = self.metadata.get(track_id=track_id)

        # get query artist
        query_artist = query.split(" - ")[0].lower()
        result_artist = single_data.artist.lower()
        if len(query_artist) < len(result_artist):
            artist_match = search(escape(query_artist), result_artist)
        else:
            artist_match = search(escape(result_artist), query_artist)

        # if search result does not match query
        # then query may be a single album
        if not artist_match and not search(single_data.title.lower(), query.lower()):
            info("Searching for album version...")
            # get album id of first result
            results = self.clients.spotify.client.search(query, type="album")

            if not results:
                info(f"{query} not found")
                return search_fallbacks(query=query, providers=self.fallback_providers)

            try:
                album_id = results["albums"]["items"][0]["id"]
            except IndexError:
                return search_fallbacks(query=query, providers=self.fallback_providers)

            # get album search function
            album_url = "https://open.spotify.com/album/" + album_id
            album = self.clients.spotify.client.album(album_url)

            if not album:
                info(f"{query} not found")
                return search_fallbacks(query=query, providers=self.fallback_providers)

            # get id of first result
            track_id = album["tracks"]["items"][0]["id"]

            return self.metadata.get(track_id=track_id)

        return single_data

